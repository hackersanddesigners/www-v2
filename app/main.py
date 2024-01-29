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
from app.file_ops import (
    file_lookup,
    search_file_content,
)
from app.build_article import make_article
from app.build_wiki import get_category
from slugify import slugify
from app.read_settings import main as read_settings
import arrow
from bs4 import BeautifulSoup
import aiofiles
from aiofiles import os as aos

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


        # `Hackers & Designers` article
        article = await make_article(home_art, client)
        article['slug'] = 'index'
        article['last_modified'] = article['metadata']['last_modified']
        article['backlinks'] = article['metadata']['backlinks']


        article['highlights'] = prepared_articles



        # list of upcoming events

        # every new article created and updated (and deleted) will be written to disk.
        # # that's our rudimentary DB that we should query more against.
        # # instead of going around and against MW APIs limitations
        # # (eg. we can query by event start and end date w/o re-installing SMW)
        # # we grep through the files for a specific pattern match:
        # # `OnDate::<YYYY/MM/DD>`
        # # `$ rg "OnDate::<current-year+month>|<next-year>" ./wiki/ --type html --files-with-matches`

        # current_timestamp = arrow.now()

        # # we do `<current-year>/<current-month>` to cut through the current's year possible
        # # result (for eg if the current time is towards the end of the year. this should
        # # make things slightly faster.
        # current_year_month = f"{current_timestamp.year}/{current_timestamp.format('MM')}/"
        # next_year = current_timestamp.shift(years=+1).year

        # pattern = f"OnDate::{current_year_month}|{next_year}/"
        # filepaths = search_file_content(pattern)
        # print(f"filepath => {filepaths}")

        # TODO: for Karl: i don't know how the design of the frontpage should be
        # when using the matching articles, so for now i didn't do any BeautifoulSoup
        # HTML extraction to fetch data from the HTML wiki articles.


        upcoming_events = []
        events_path = file_lookup("events")

        if (events_path[0]):
            if await aos.path.exists(events_path[0]):
                async with aiofiles.open(events_path[0], mode='r') as f:
                    tree = await f.read()
                    soup = BeautifulSoup(tree, 'lxml')
                    upcoming_events = soup.find_all("article", {"class": "when-upcoming" })
                    upcoming_events_str = []
                    for x in upcoming_events:
                        upcoming_events_str.append(str(x))

        article['upcoming'] = upcoming_events_str

        print( json.dumps( article, indent=2 ) )

        return templates.TemplateResponse("index.html",
                                          {"request": request,
                                           "article": article})


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
                matching_uri = Path(matches[0]).stem

                print(f"uri-redirect => {uri}\n",
                      f"=> {new_uri}\n",
                      f"matches => {matches}\n"
                      f"r => {matching_uri}")

                redirect_uri = f"/{matching_uri}"
                return RedirectResponse(url=redirect_uri, status_code=307)

            else:
                return RedirectResponse(url="/not-found", status_code=307)

    
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

        with open(file_path) as f:
            return f.read()

    except FileNotFoundError:
        print(f"return 404")

        raise HTTPException(status_code=404)
