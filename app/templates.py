from dotenv import load_dotenv
import os
import asyncio
from jinja2 import Environment, FileSystemLoader
from slugify import slugify
from write_to_disk import main as write_to_disk
load_dotenv()


def make_url_slug(url: str):
    return slugify(url)


async def make_index(articles):
    env = Environment(loader=FileSystemLoader('app/templates'), autoescape=True)
    env.filters['slug'] = make_url_slug
    t = env.get_template('index.html')

    article = {
        'title': 'Index',
        'slug': 'index',
        'articles': articles
    }

    sem = asyncio.Semaphore(int(os.getenv('SEMAPHORE')))
    document = t.render(article=article)
    await write_to_disk(article['slug'], document, sem)
