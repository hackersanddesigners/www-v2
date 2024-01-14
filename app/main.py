from dotenv import load_dotenv
import os
import json
import asyncio
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
    query_check,
)
import httpx
from app.fetch import (
    create_context,
    query_continue,
    query_wiki,
    fetch_category,
)
from app.file_ops import file_lookup
from app.build_article import make_article
from app.build_wiki import get_category
from slugify import slugify
from app.read_settings import main as read_settings
load_dotenv()


app = FastAPI()

base_dir = Path.cwd()

templates = Jinja2Templates(directory=Path(__file__).parent / "views" / "templates")
templates.env.filters['slug'] = make_url_slug
templates.env.filters['ts'] = make_timestamp
templates.env.filters['query_check'] = query_check


app.mount("/static",
          StaticFiles(directory=Path(__file__).parent.parent / "static"),
          name="static")
app.mount("/static/media",
          StaticFiles(directory=base_dir / "wiki/static/media"),
          name="media")


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
    fetch and return Hackers & Designers article
    """

    home_art = config['wiki']['frontpage']['article']
    home_cat = config['wiki']['frontpage']['category']
      
    context = create_context(ENV)
    timeout = httpx.Timeout(10.0, connect=60.0)
    async with httpx.AsyncClient(verify=context) as client:

        # list of articles w/ `highlight` cat
        data = await fetch_category(home_cat, client)
        art_tasks = []
        for article in data:
            task = make_article(article['title'], client)
            art_tasks.append(asyncio.ensure_future(task))

        prepared_articles = await asyncio.gather(*art_tasks)
        prepared_articles = [item for item
                             in prepared_articles 
                             if item is not None]

        print(f"prepared-articles => {prepared_articles}")        

        # `Hackers & Designers` article
        article = await make_article(home_art, client)
        article['slug'] = 'index'
        article['last_modified'] = article['metadata']['last_modified']
        article['backlinks'] = article['metadata']['backlinks']

        return templates.TemplateResponse("index.html",
                                          {"request": request,
                                           "article": article})


# @app.middleware("http")
# async def redirect_uri(request: Request, call_next):
#     """
#     Middleware to check incoming URL and do an article look-up
#     to see if anything matches from the local filesystem wiki.
#     If anything matches, redirects the incoming request to the
#     correct URL.
#     """

#     # this is done to figure out which category each article belongs to.
#     # as of <2023-08-22> this is useful for when we add a backlink URL,
#     # for which we don't have a category by default. we could parse this
#     # when retrieve the set of backlinks, but it is pretty wasteful.
#     # ideally this can be solved by rather having an sqlite cache layer.

#     uri = request.url.path[1:]
#     uri = uri.replace('.html', '')
#     uri_first = uri.split('/')[0]

#     # build a list of categories, plus other items that might appear
#     # as first item in the URI (eg. `/static`)
#     cats = config['wiki']['categories']
#     uri_list = [cat['label'].lower() for cat in cats.values()]
#     uri_list.append('static')
    
#     if uri_first not in uri_list:
#         matches = file_lookup(uri)

#         if len(matches) > 0:
#             filename = str(matches[0]).split('.')[0]
#             new_url = "/".join(filename.split('/')[1:])
#             redirect_url = f"/{new_url}"
#             return RedirectResponse(url=redirect_url)
        

#     response = await call_next(request)
#     return response


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

        with open(file_path) as f:
            return f.read()

    except FileNotFoundError:
        print(f"return 404")

        raise HTTPException(status_code=404)
