from dotenv import load_dotenv
import os
import json
import asyncio
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from .templates import (
    make_url_slug,
    make_timestamp,
    make_event_index,
    make_collaborators_index,
    make_publishing_index,
    make_tool_index,
)
import httpx
from .fetch import create_context
from .build_article import make_article 
from .build_wiki import get_category
import tomli
from slugify import slugify
load_dotenv()


app = FastAPI()

base_dir = Path.cwd()

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.filters['slug'] = make_url_slug
templates.env.filters['ts'] = make_timestamp

# app.mount("/",
#           StaticFiles(directory=base_dir / "wiki", html=True),
#           name="wiki")
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

cats = config['wiki']['categories']


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
async def category(request: Request, cat: str):
    """
    build index page for given category
    """
    
    print(f"cat => {cat}")

    index = await get_category(ENV, URL, cat)
    index = index[cat]

    sem = None
    context = create_context(ENV)
    async with httpx.AsyncClient(verify=context) as client:

        metadata_only = True
        art_tasks = []
        for article in index:
            print(f"{article}")
            task = make_article(article['title'], client, metadata_only)
            art_tasks.append(asyncio.ensure_future(task))

            prepared_articles = await asyncio.gather(*art_tasks)
            print(f"articles: {len(prepared_articles)}")


        article = None
        if cat == 'event':
            article = await make_event_index(prepared_articles, cat)

        elif cat == 'collaborators':
            article = await make_collaborators_index(prepared_articles, cat)

        elif cat == 'publishing':
            article = await make_publishing_index(prepared_articles, cat)

        elif cat == 'tools':
            article = await make_tool_index(prepared_articles, cat)

        if article is not None:
            return templates.TemplateResponse(f"{cat}-index.html",
                                              {"request": request,
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
