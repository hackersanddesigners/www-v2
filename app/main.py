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
)
import httpx
from .fetch import create_context
from .build_article import make_article 
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


