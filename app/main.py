from dotenv import load_dotenv
import os
import json
import asyncio
from fastapi import FastAPI, Request, HTTPException
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
)
import httpx
from app.fetch import (
    create_context,
    query_continue,
    query_wiki,
)
from app.file_ops import file_lookup
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


app.mount("/static",
          StaticFiles(directory=Path(__file__).parent.parent / "static"),
          name="static")
app.mount("/static/media",
          StaticFiles(directory=base_dir / "wiki/static/media"),
          name="media")


ENV = os.getenv('ENV')
URL = os.getenv('BASE_URL')


with open("settings.toml", mode="rb") as f:
    config = tomli.load(f)
    

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


@app.middleware("http")
async def redirect_uri(request: Request, call_next):
    """
    Middleware to check incoming URL and do an article look-up
    to see if anything matches from the local filesystem wiki.
    If anything matches, redirects the incoming request to the
    correct URL.
    """

    # this is done to figure out which category each article belongs to.
    # as of <2023-08-22> this is useful for when we add a backlink URL,
    # for which we don't have a category by default. we could parse this
    # when retrieve the set of backlinks, but it is pretty wasteful.
    # ideally this can be solved by rather having an sqlite cache layer.

    uri = request.url.path[1:]
    uri = uri.replace('.html', '')
    uri_first = uri.split('/')[0]

    # build a list of categories, plus other items that might appear
    # as first item in the URI (eg. `/static`)
    cats = config['wiki']['categories']
    uri_list = [cat['label'].lower() for cat in cats.values()]
    uri_list.append('static')
    
    if uri_first not in uri_list:
        matches = file_lookup(uri)

        if len(matches) > 0:
            filename = str(matches[0]).split('.')[0]
            new_url = "/".join(filename.split('/')[1:])
            redirect_url = f"/{new_url}"
            return RedirectResponse(url=redirect_url)
        

    response = await call_next(request)
    return response


@app.get("/search", response_class=HTMLResponse)
async def search(request: Request, query: str):
    """
    initiate wiki search on website
    """

    # check if exact slug is matches rendered HTML page and redirect to it

    results = await query_wiki(ENV, URL, query)
    article = await make_search_index(results, query)

    return templates.TemplateResponse("search-index.html",
                                      {"request": request,
                                       "article": article})


@app.get("/{cat}", response_class=HTMLResponse)
async def category(request: Request,
                   cat: str,
                   page: int | None = 0,
                   sort_by: str | None = None,
                   sort_dir: str | None = None):
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
            save_to_disk = False

            # -- <2023-09-27> we remove the sorting option as for
            #    performance reasons we do the sorting only on the
            #    paginated subset of articles (because we need to parse
            #    each article to retrieve the date field, etc).
            #    given it's not particularly useful in retrospect
            #    we keep the code but disable it.
            
            # sort_dir = True if sort_dir == 'desc' else False
            # sorting = (sort_by, sort_dir)
            sorting = None
            
            if cat_label == 'Events':
                article = await make_event_index(prepared_articles, cat_key, cat_label, save_to_disk, sorting)
                
            elif cat_label == 'Collaborators':
                article = await make_collaborators_index(prepared_articles, cat, cat_label)

            elif cat_label == 'Publishing':
                article = await make_publishing_index(prepared_articles, cat, cat_label, save_to_disk)

            elif cat_label == 'Tools':
                article = await make_tool_index(prepared_articles, cat, cat_label, save_to_disk, sorting)

            elif cat_label == 'Articles':
                article = await make_article_index(prepared_articles, cat, cat_label)
            

            if article:
                return templates.TemplateResponse(f"{slugify(cat_key)}-index.html",
                                                  {"request": request,
                                                   "pagination": pagination,
                                                   "category": slugify(cat_label),
                                                   "article": article})


@app.get("/{cat}/{article}", response_class=HTMLResponse)
async def article(request: Request, cat: str, article: str):
    """
    return HTML article from disk
    """

    try:
        WIKI_DIR = os.getenv('WIKI_DIR')
        filename = Path(article).stem
        file_path = f"{WIKI_DIR}/{cat}/{slugify(filename)}.html"

        with open(file_path) as f:
            return f.read()

    except FileNotFoundError:
        print(f"return 404")

        raise HTTPException(status_code=404)
