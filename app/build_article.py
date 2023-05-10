from fetch import fetch_article
from parser import parser
from bs4 import BeautifulSoup
from slugify import slugify
import aiofiles
from aiofiles import os
from write_to_disk import main as write_to_disk
import tomli


def make_nav():
    """
    make a list of dictionaries {label, uri} as links
    to listed categories in settings.toml
    """

    with open("settings.toml", mode="rb") as f:
        config = tomli.load(f)

    # cats = config['wiki']['categories']
    cats = config['wiki']['indexes']
    nav = []
    for cat in cats:
        nav.append({ "label": cat,
                      "uri": f"/{slugify(cat)}.html" })

    return nav


async def get_article(page_title: str, client):

    article, backlinks, redirect_target = await fetch_article(page_title, client)

    if article is not None:
        return article

    else:
        print(f"{page_title} return empty")
        return None


def get_article_field(field, article):

    if field in article:
        return article[field]
    else:
        return None


async def make_article(page_title: str, client, metadata_only: bool):

    article, backlinks, redirect_target = await fetch_article(page_title, client)
    nav = make_nav()

    if article is not None:

        last_modified = article['revisions'][0]['timestamp']

        if metadata_only:
            metadata, images, tool_metadata = await parser(article, metadata_only, redirect_target)

            article_metadata = {
                "title": article['title'],
                "images": images,
                "metadata": metadata,
                "last_modified": last_modified,
                "backlinks": backlinks,
                "tool": tool_metadata,
            }

            return article_metadata


        body_html, metadata = await parser(article, metadata_only, redirect_target)

        article_html = {
            "title": page_title,
            "html": body_html,
            "slug": slugify(page_title),
            "nav": nav
        }

        article_metadata = {
            "title": article['title'],
            "images": get_article_field('images', article),
            "template": get_article_field('template', article),
            "metadata": metadata,
            "last_modified": last_modified,
            "backlinks": backlinks,
            "nav": nav
        }

        return article_html, article_metadata

    else:
        # TODO handle article remove from local wiki
        print('article not found! it could have been deleted meanwhile\n and we got notified about it')

        # check if there's a copy of article in `wiki/` and
        # if yes, remove it?

        print(f":: article is none (?) => {page_title}")

        try:
            await delete_article(page_title)

        except Exception as e:
            print(f"delete article err => {e}")


async def redirect_article(page_title: str, redirect_target: str):

    fn = f"./wiki/{slugify(page_title)}.html"
    print(f"redirect-article => {fn}")

    if await os.path.exists(fn):
        async with aiofiles.open(fn, mode='r') as f:
            tree = await f.read()
            soup = BeautifulSoup(tree, 'lxml')
            
            main_h1 = soup.body.main.h1
            redirect = f"<p>This page has been moved to <a href=\"{slugify(redirect_target)}.html\">{redirect_target}</a>.</p>"

            main_h1.insert_after(redirect)
            output = soup.prettify(formatter=None)

        async with aiofiles.open(fn, mode='w') as f:
            await f.write(output)

    else:
        print(f"redirect-article: {page_title} not found, nothing done")


async def save_article(article: str | None, template, sem):

    if article is not None:
        filters = {
            'slug': make_url_slug,
            'ts': make_timestamp,
        }

        document = template.render(article=article)
        await write_to_disk(article['slug'], document, sem)


async def delete_article(page_title: str):
    """
    remove local wiki article, if it exists
    """

    fn = f"wiki/{slugify(page_title)}.html"

    if await os.path.exists(fn):
        await os.remove(fn)
        print(f"delete-article: {page_title} removed")

    else:
        print(f"delete-article: {page_title} not found, nothing done")
