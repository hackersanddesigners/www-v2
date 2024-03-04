import os
from pathlib import Path

import aiofiles
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slugify import slugify
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.fetch import query_wiki
from app.file_ops import file_lookup
from app.read_settings import main as read_settings

from .views.template_utils import (
    make_timestamp,
    make_timestamp_friendly,
    make_url_slug,
    paginator,
)
from .views.views import make_error_page, make_search_index

load_dotenv()


app = FastAPI()

base_dir = Path.cwd()

templates = Jinja2Templates(directory=Path(__file__).parent / "views" / "templates")
templates.env.filters["slug"] = make_url_slug
templates.env.filters["ts"] = make_timestamp
templates.env.filters["tsh"] = make_timestamp_friendly


app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent.parent / "static"),
    name="static",
)


ENV = os.getenv("ENV")
URL = os.getenv("BASE_URL")


config = read_settings()


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    """
    Custom HTTP handler function to display custom
    user-facing error messages (HTTP code, HTML response).
    """

    if exc.status_code == 404:
        message = "Nothing was found here."
    elif exc.status_code == 500:
        message = "Server error."
    elif 400 <= exc.status_code <= 499:
        message = "Generic error."

    article = await make_error_page(exc.status_code, message)

    t = templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "article": article,
        },
    )

    return HTMLResponse(content=t.body, status_code=exc.status_code)


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """
    Read from WIKI_DIR and return index.html.
    """

    try:
        WIKI_DIR = os.getenv("WIKI_DIR")
        file_path = f"{WIKI_DIR}/index.html"

        async with aiofiles.open(file_path, mode="r") as f:
            return await f.read()

    except FileNotFoundError:
        print("return 404")

        raise HTTPException(status_code=404)


@app.middleware("http")
async def redirect_uri(request: Request, call_next):
    """
    Check if incoming URI is formatted in the previous
    hd-www-v1 style (eg had-py) — below for examples.
    Rewrite URI to match a possible wiki article on disk.
    """

    uri = request.url.path[1:]

    # ignore URI to static assets
    if not uri.startswith("static"):

        # -- examples of old-style URIs:
        # p/About
        # s/Collaborators
        # special case:
        # - s/Summer_Camp_2023 => activities?type=hdsc2023
        # - s/Summer_Camp_2023/p/Open_Call!_H%26D_Summer_Camp_2023_-_HopePunk%3A_Reknitting_Collective_Infrastructures
        # - s/Summer_Camp_2023/p/Coding_in_Situ

        tokens = uri.split("/")

        if len(tokens) > 1:
            new_uri = slugify(tokens[-1])
            matches = file_lookup(new_uri)
            if len(matches) > 0:
                redirect_uri = Path(matches[0]).stem

                print(
                    f"uri-redirect => {uri}\n",
                    f"=> {new_uri}\n",
                    f"matches => {matches}\n" f"r => {redirect_uri}",
                )

                return RedirectResponse(url=f"/{redirect_uri}", status_code=301)

            elif new_uri.startswith("summer-academy") or new_uri.startswith(
                "summer-camp"
            ):

                summer_tokens = new_uri.split("-")
                summer_type = summer_tokens[-2][0].lower()
                summer_year = summer_tokens[-1]
                event_label = slugify(config["wiki"]["categories"]["Event"]["label"])

                redirect_uri = f"{event_label}?type=hds{summer_type}{summer_year}"

                print(
                    f"uri-redirect => {uri}\n",
                    f"=> {new_uri}\n",
                    f"r => {redirect_uri}",
                )

                return RedirectResponse(url=f"/{redirect_uri}", status_code=308)

            else:
                return RedirectResponse(url=f"/{new_uri}", status_code=301)

    # --
    response = await call_next(request)
    return response


@app.get("/search", response_class=HTMLResponse)
async def search(request: Request, query: str, page: int | None = 0):
    """
    Run a search query on MediaWiki's APIs and display
    results back.
    """

    # check if exact slug is matches rendered HTML page and redirect to it

    results = await query_wiki(ENV, URL, query)

    # -- make pagination
    pagination = paginator(results, 5, page)

    article = await make_search_index(pagination["data"], query)

    return templates.TemplateResponse(
        "search-index.html",
        {"request": request, "article": article, "pagination": pagination},
    )


@app.get("/{article}", response_class=HTMLResponse)
async def article(request: Request, article: str):
    """
    Read from WIKI_DIR and return matching HTML article.
    """

    try:
        WIKI_DIR = os.getenv("WIKI_DIR")
        filename = Path(article).stem
        file_path = f"{WIKI_DIR}/{slugify(filename)}.html"

        async with aiofiles.open(file_path, mode="r") as f:
            return await f.read()

    except FileNotFoundError:
        print("return 404")

        raise HTTPException(status_code=404)
