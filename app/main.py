from dotenv import load_dotenv
import os
import json
import asyncio
import aiofiles
from aiofiles import os as aos
from fastapi import (
    FastAPI,
    Request,
    HTTPException,
)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
)
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.templating import Jinja2Templates
from pathlib import Path
from .views.views import (
    make_front_index,
    make_event_index,
    make_collaborators_index,
    make_publishing_index,
    make_tool_index,
    make_article_index,
    make_search_index,
)
from .views.template_utils import (
    make_url_slug,
    make_timestamp,
    paginator,
)
import httpx
from app.fetch import (
    create_context,
    query_continue,
    query_wiki,
    fetch_category,
)
from app.file_ops import (
    file_lookup,
    search_file_content,
)
from app.build_article import make_article
from app.build_wiki import get_category
from slugify import slugify
from app.read_settings import main as read_settings
import arrow


load_dotenv()


app = FastAPI()

base_dir = Path.cwd()

templates = Jinja2Templates(directory=Path(__file__).parent / "views" / "templates")
templates.env.filters['slug'] = make_url_slug
templates.env.filters['ts'] = make_timestamp


app.mount("/static",
          StaticFiles(directory=Path(__file__).parent.parent / "static"),
          name="static")


ENV = os.getenv('ENV')
URL = os.getenv('BASE_URL')


config = read_settings()


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):

    if exc.status_code == 404:
        message = "Nothing was found here."
    elif exc.status_code == 500:
        message = "Server error."
    elif 400 <= exc.status_code <= 499:
        message = "Generic error."

    article = {
        "title": "Error",
        "message": message,
    }

    t = templates.TemplateResponse("error.html",
                                   {"request": request,
                                    "article": article,
                                    })

    return HTMLResponse(content=t.body, status_code=exc.status_code)


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """
    fetch and return index.html
    """

    try:
        WIKI_DIR = os.getenv('WIKI_DIR')
        file_path = f"{WIKI_DIR}/index.html"

        async with aiofiles.open(file_path, mode='r') as f:
            return await f.read()

    except FileNotFoundError:
        print(f"return 404")

        raise HTTPException(status_code=404)


@app.middleware("http")
async def redirect_uri(request: Request, call_next):
    """
    Check if incoming URI is formatted in the previous style
    (see below for examples), and rewrite it to match
    a possible wiki article on disk.
    """

    uri = request.url.path[1:]

    # ignore URI to static assets
    if not uri.startswith('static'):

        # -- examples of old-style URIs:
        # p/About
        # s/Collaborators
        # s/Summer_Camp_2023/p/Open_Call!_H%26D_Summer_Camp_2023_-_HopePunk%3A_Reknitting_Collective_Infrastructures
        # s/Summer_Camp_2023/p/Coding_in_Situ

        tokens = uri.split('/')
        if len(tokens) > 1:
            new_uri = slugify(tokens[-1])

            matches = file_lookup(new_uri)
            if len(matches) > 0:
                redirect_uri = Path(matches[0]).stem

                print(f"uri-redirect => {uri}\n",
                      f"=> {new_uri}\n",
                      f"matches => {matches}\n"
                      f"r => {redirect_uri}")

                return RedirectResponse(url=f"/{redirect_uri}", status_code=301)

            else:
                return RedirectResponse(url=f"/{new_uri}", status_code=301)

    
    # -- 
    response = await call_next(request)
    return response


@app.get("/search", response_class=HTMLResponse)
async def search(request: Request,
                 query: str,
                 page: int | None = 0):
    """
    initiate wiki search on website
    """

    # check if exact slug is matches rendered HTML page and redirect to it

    results = await query_wiki(ENV, URL, query)

    # -- make pagination
    pagination = paginator(results, 5, page)

    article = await make_search_index(pagination['data'], query)

    return templates.TemplateResponse("search-index.html",
                                      {"request": request,
                                       "article": article,
                                       "pagination": pagination})


@app.get("/{article}", response_class=HTMLResponse)
async def article(request: Request, article: str):
    """
    return HTML article from disk
    """

    try:
        WIKI_DIR = os.getenv('WIKI_DIR')
        filename = Path(article).stem
        file_path = f"{WIKI_DIR}/{slugify(filename)}.html"

        async with aiofiles.open(file_path, mode='r') as f:
            return await f.read()

    except FileNotFoundError:
        print(f"return 404")

        raise HTTPException(status_code=404)
