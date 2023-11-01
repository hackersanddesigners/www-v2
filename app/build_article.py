import os
from app.fetch import fetch_article
from app.parser import parser
from bs4 import BeautifulSoup
from slugify import slugify
import aiofiles
from aiofiles import os as aos
from app.write_to_disk import main as write_to_disk
import tomli
from app.views.template_utils import (
    make_url_slug,
    make_timestamp,
)
from pathlib import Path
from app.read_settings import main as read_settings
from app.file_ops import file_lookup


WIKI_DIR = Path(os.getenv('WIKI_DIR'))
config = read_settings()

with open("settings.toml", mode="rb") as f:
    config = tomli.load(f)

def make_nav():
    """
    make a list of dictionaries {label, uri} as links
    to listed categories in settings.toml
    """

    cats = config['wiki']['categories']

    nav = []
    for k, v in cats.items():
        nav.append({ "label": v['label'],
                      "uri": f"/{slugify(v['label'])}" })

    return nav


async def get_article(page_title: str, client):

    article, backlinks, redirect_target = await fetch_article(page_title, client)

    if article is not None:
        return article

    else:
        print(f"{page_title} return empty")
        return None


def get_article_field(field: str, article):

    if field in article:
        return article[field]

    else:
        return None


def get_translations(page_title: str, backlinks: list[str]) -> list[str]:
    """
    Return list of URLs pointing to translations of the given article.
    """

    translations = config['wiki']['translation_langs']
    matches = [f"{page_title}/{lang}" for lang in translations]

    return [page['title'] for page in backlinks
            if page['title'] in matches]


async def make_article(page_title: str, client, metadata_only: bool):

    article, backlinks, redirect_target = await fetch_article(page_title, client)

    article_translations = []
    if backlinks:
        article_translations = get_translations(page_title, backlinks)

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
                "translations": article_translations,
            }

            return article_metadata


        body_html, metadata = await parser(article, metadata_only, redirect_target)

        article_html = {
            "title": page_title,
            "wiki_styles_path": f"/assets/styles/{ config['wiki']['stylespage'] }.css",
            "html": body_html,
            "slug": slugify(page_title),
            "nav": nav,
            "translations": article_translations,
        }

        article_metadata = {
            "title": article['title'],
            "images": get_article_field('images', article),
            "template": get_article_field('template', article),
            "metadata": metadata,
            "last_modified": last_modified,
            "backlinks": backlinks,
            "nav": nav,
            "translations": article_translations,
        }

        return article_html, article_metadata

    else:
        print('article not found! it could have been deleted meanwhile\n and we got notified about it')

        # check if there's a copy of article in `wiki/` and
        # if yes, remove it?

        print(f":: article is none (?) => {page_title}")

        try:
            await delete_article(page_title)

        except Exception as e:
            print(f"delete article err => {e}")


async def redirect_article(article_title: str, redirect_target: str):
    """
    """

    p = Path(article_title)
    filename = slugify(str(p.stem))
    paths = file_lookup(filename)

    if len(paths) > 0:
        fn = paths[0]

        if await aos.path.exists(fn):
            async with aiofiles.open(fn, mode='r') as f:
                tree = await f.read()
                soup = BeautifulSoup(tree, 'lxml')

                main_h1 = soup.body.main.h1
                redirect = f"<p>This page has been moved to <a href=\"{slugify(redirect_target)}.html\">{redirect_target}</a>.</p>"

                main_h1.insert_after(redirect)
                output = soup.prettify(formatter=None)

            async with aiofiles.open(fn, mode='w') as f:
                await f.write(output)

            return f"{fn.parent.stem}/{fn.stem}"

        else:
            print(f"redirect-article: {article_title} not found, nothing done")


async def save_article(article: str | None, filepath: str, template, sem, ext):

    if article is not None:
        filters = {
            'slug': make_url_slug,
            'ts': make_timestamp,
            }
        document = template.render(article=article)
        await write_to_disk(filepath, document, sem, ext)


async def delete_article(article_title: str, cat: str | None = None):
    """
    pass article title and remove it from local wiki dir, if it exists.

    let's construct the correct filepath in here
    instead of demanding the requiring function to
    do it; in this way we uniformize what we need it
    and just assume we receive the title of the article
    and potentially its cat; if cat is None we scan the
    WIKI_DIR for a matching filename.
    """

    print(f"delete-article => {article_title, cat}")

    p = Path(article_title)
    filename = slugify(str(p.stem))

    if cat:
        fn = f"{WIKI_DIR}/{cat}/{filename}.html"
    else:
        paths = file_lookup(filename)

        print(f"delete-article => scan for full filepath => {paths}")
        if len(paths) > 0:
            fn = paths[0]
        else:
            print(f"delete-article => scan-dir found no article match for {filename}")
            return

    if await aos.path.exists(fn):
        await aos.remove(fn)
        print(f"delete-article: {article_title} removed")

    else:
        print(f"delete-article: {article_title} not found, nothing done")


async def has_duplicates(article_filename: str, matching_cat: str):
    """
    after an article update, check if the embedded category has changed and if true,
    scan across all category subfolders except the new category to check if
    a previous version of the article has been left behind.
    """

    # build list of paths under each subdir except the one matching cat_key
    # and filter out any path matching <cat>/article_filepath, where cat
    # is not matching_cat

    print(f"check if article has duplicates... => {article_filename, matching_cat}")

    pattern = "**/*.html"
    paths = [p for p
             in WIKI_DIR.glob(pattern)
             if article_filename in str(p) and not p.parent.stem == matching_cat]

    if len(paths) > 0:
        print(f"remove these filepaths {paths}!")

        for p in paths:
            cat = str(p.parent.stem)
            fn = str(p.stem)
            await delete_article(fn, cat)

    else:
        print(f"no duplicates...")
        return
