from dotenv import load_dotenv
import os
import asyncio
from jinja2 import Environment, FileSystemLoader
from slugify import slugify
from write_to_disk import main as write_to_disk
load_dotenv()


def get_template(template: str, filters):
    env = Environment(loader=FileSystemLoader('app/templates'), autoescape=True)
    if filters is not None:
        for k,v in filters.items():
            env.filters[k] = v

    t = env.get_template(f"{template}.html")
    return t
    

def make_url_slug(url: str):
    if url:
        return slugify(url)
    return url


async def make_index(articles):
    filters = {'slug': make_url_slug}
    template = get_template('index', filters)

    article = {
        'title': 'Index',
        'slug': 'index',
        'articles': articles
    }

    sem = None
    document = template.render(article=article)
    await write_to_disk(article['slug'], document, sem)
