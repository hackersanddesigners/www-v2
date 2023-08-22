from dotenv import load_dotenv
import os
import json
import asyncio
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from starlette.exceptions import HTTPException
from fastapi.templating import Jinja2Templates
from pathlib import Path
from .views.views import (
    make_event_index,
    make_collaborators_index,
    make_publishing_index,
    make_tool_index,
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
)
from app.build_article import make_article 
from app.build_wiki import get_category
import tomli
from slugify import slugify
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
app.mount("/assets/media",
          StaticFiles(directory=base_dir / "wiki/assets/media"),
          name="media")


ENV = os.getenv('ENV')
URL = os.getenv('BASE_URL')


with open("settings.toml", mode="rb") as f:
    config = tomli.load(f)


async def not_found(request: Request, exc: HTTPException):
    return HTMLResponse(content=HTML_404_PAGE, status_code=exc.status_code)

async def server_error(request: Request, exc: HTTPException):
    return HTMLResponse(content=HTML_500_PAGE, status_code=exc.status_code)


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """
    fetch and return Hackers & Designers article
    """

    sem = None
    context = create_context(ENV)
    async with httpx.AsyncClient(verify=context) as client:

        frontpage = {"news": None, "upcoming_events": []} 

        metadata_only = False
        article, metadata = await make_article("Hackers & Designers", client, metadata_only)

        article['slug'] = 'index'
        article['last_modified'] = metadata['last_modified']
        article['backlinks'] = metadata['backlinks']

        return templates.TemplateResponse("index.html",
                                          {"request": request,
                                           "article": article})


@app.get("/{cat}", response_class=HTMLResponse)
async def category(request: Request, cat: str, page: int | None = 0, sort_by: str | None = None):
    """
    build index page for given category: we build a paginated
    template instead of fetching through all the results of a category
    in one go.
    """
    
    cats = config['wiki']['categories']

    cat_key = None
    cat_label = None
    for k, v in cats.items():
        if cats[k]['label'].lower() == cat:
            cat_key = k
            cat_label = cats[k]['label']

    if not cat_key:
        raise HTTPException(status_code=404)
    
    else:

        params = {
            'action': 'query',
            'list': 'categorymembers',
            'cmtitle': f"Category:{cat_key}",
            'cmlimit': '50',
            'cmprop': 'ids|title|timestamp',
            'formatversion': '2',
            'format': 'json',
            'redirects': '1',
        }

        context = create_context(ENV)
        timeout = httpx.Timeout(10.0, connect=60.0)
        async with httpx.AsyncClient(verify=context) as client:

            # -- get full list of entries from category
            data = []
            async for response in query_continue(client, URL, params):

                response = response['categorymembers']
                if len(response) > 0 and 'missing' in response[0]:
                    title = response[0]['title']
                    print(f"the page could not be found => {title}")
            
                else:
                    data.extend(response)

            # -- make pagination
            pagination = paginator(data, 50, page)
                    
            metadata_only = True
            art_tasks = []
            for article in pagination['data']:
                task = make_article(article['title'], client, metadata_only)
                art_tasks.append(asyncio.ensure_future(task))

            prepared_articles = await asyncio.gather(*art_tasks)

            article = None
            if cat_key == 'Event':
                article = await make_event_index(prepared_articles, cat_key, cat_label, False, sort_by)
                
            elif cat_label == 'Collaborators':
                article = await make_collaborators_index(prepared_articles, cat, cat_label)

            elif cat_label == 'Publishing':
                article = await make_publishing_index(prepared_articles, cat, cat_label)

            elif cat_label == 'Tools':
                article = await make_tool_index(prepared_articles, cat, cat_label)

            if article:
                return templates.TemplateResponse(f"{slugify(cat_key)}-index.html",
                                                  {"request": request,
                                                   "pagination": pagination,
                                                   "article": article})


@app.get("/{cat}/{article}", response_class=HTMLResponse)
async def article(request: Request, cat: str, article: str):
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
