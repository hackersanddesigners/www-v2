import asyncio
import os
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.build_article import make_article
from app.fetch import create_context, query_continue
from app.file_ops import write_to_disk
from app.log_to_file import main as log
from app.read_settings import main as read_settings
from app.views.template_utils import get_template
from app.views.views import (
    make_article_event,
    make_article_index,
    make_collaborators_index,
    make_event_index,
    make_publishing_index,
    make_tool_index,
)

ENV = os.getenv("ENV")
URL = os.getenv("BASE_URL")
WIKI_DIR = os.getenv("WIKI_DIR")
config = read_settings()


def check_if_cat_exists(cat: str) -> tuple[str | None, str | None]:
    """
    Check if given cat exists in settings.toml.
    Check if:
    - index is True (if False we don't want
      to build index page for it)
    - given cat match any of the set category
      so we can fetch the label value
    """

    cat_key = None
    cat_label = None

    cats = config["wiki"]["categories"]

    for k, v in cats.items():
        if v["index"] and cat == k.lower():
            cat_key = k
            cat_label = cats[k]["label"]

    if not cat_key:
        print(
            f"make-category-index: the 'cat: {cat}' has not matched with any\n",
            "of the following categories:\n",
            f"{list(cats.keys())}",
        )

    return cat_key, cat_label


async def get_category(
    ENV: str | None, URL: str | None, cat: str
) -> dict[str, list[Any]] | bool:
    """
    Fetch all articles from the given cat.
    """

    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": f"Category:{cat}",
        "cmlimit": "50",
        "cmprop": "ids|title|timestamp",
        "formatversion": "2",
        "format": "json",
        "redirects": "1",
    }

    context = create_context(ENV)
    timeout = httpx.Timeout(10.0, connect=60.0, read=60.0)
    async with httpx.AsyncClient(verify=context, timeout=timeout) as client:

        # -- get full list of entries from category
        data = {cat: []}
        async for response in query_continue(client, URL, params):
            response = response["categorymembers"]

            if len(response) > 0 and "missing" in response[0]:
                title = response[0]["title"]
                print(f"the page could not be found => {title}")

            else:
                data[cat].extend(response)

    return data


async def make_category_index(
    cat: str,
) -> dict[str, list[str] | list[dict[str, str]]] | None:
    """
    Build Index page of the specified category.
    """

    cat_key, cat_label = check_if_cat_exists(cat)

    langs = config["wiki"]["langs"]

    category_data = await get_category(ENV, URL, cat_key)
    articles = category_data[cat_key]

    context = create_context(ENV)
    timeout = httpx.Timeout(10.0, connect=60.0, read=60.0)
    async with httpx.AsyncClient(verify=context, timeout=timeout) as client:

        art_tasks = []
        for article in articles:
            # filter out translated article
            title = article["title"]
            lang_stem = title.split("/")[-1]

            if lang_stem not in langs:
                task = make_article(article["title"], client)
                art_tasks.append(asyncio.ensure_future(task))

        prepared_articles = await asyncio.gather(*art_tasks)
        await log(
            "info",
            f"prep-articles {cat_key} => un-filtered {len(prepared_articles)}\n",
            sem=None,
        )

        prepared_articles = [item for item in prepared_articles if item is not None]
        await log(
            "info",
            f"prep-articles {cat_key} => filtered {len(prepared_articles)}\n",
            sem=None,
        )

        # -- prepare per-template category article
        article = None

        if cat_key == "Event":
            article = await make_event_index(prepared_articles, cat_key, cat_label)

        elif cat_key == "Collaborators":
            article = await make_collaborators_index(
                prepared_articles, cat_key, cat_label
            )

        elif cat_key == "Publishing":
            article = await make_publishing_index(prepared_articles, cat_key, cat_label)

        elif cat_key == "Tools":
            article = await make_tool_index(prepared_articles, cat_key, cat_label)

        elif cat_key == "Article":
            article = await make_article_index(prepared_articles, cat_key, cat_label)

        return article


async def build_categories(
    categories: list[str], sem: asyncio.Semaphore | None
) -> None:
    """
    Build index page for all categories.
    """

    cat_tasks = []
    for cat in categories:
        task = make_category_index(cat)
        cat_tasks.append(asyncio.ensure_future(task))

    prepared_category_indexes = await asyncio.gather(*cat_tasks)
    prepared_category_indexes = [
        item for item in prepared_category_indexes if item is not None
    ]

    cat_tasks_html = []
    for cat_index in prepared_category_indexes:
        filepath = f"{cat_index['slug']}"
        task = write_to_disk(filepath, cat_index["html"], sem)
        cat_tasks_html.append(asyncio.ensure_future(task))

    await asyncio.gather(*cat_tasks_html)


async def update_categories(
    article: dict[str, list[str] | list[dict[str, str]]]
) -> None:
    """
    Update Index page for each category defined in settings.toml.
    We don't rebuild the whole Index page from scratch by parsing every
    article in it. Rather, we just update the article's info
    in the Index page that has triggered the update_categories function.
    """

    # - select index-template by `cat`
    # - build updated article item HTML snippet for category index
    # - use bs4 to search and replace previous article-item with new one

    cat_tasks_html = []

    cat_label = None
    for cat in article["metadata"]["categories"]:

        cat_key, cat_label = check_if_cat_exists(cat)

        if cat_label:
            # if article is an `event` we need to do more work
            # on the data structure before we pass it to the template.
            # do it here.
            prepared_article = article
            if cat == "event":
                prepared_article = make_article_event(article)

            # make new snippet for updated article
            template = get_template(f"partials/{cat}-item")
            snippet_new = template.render(article=prepared_article)

            # make bs4 object out of the HTML string
            snippet_new = BeautifulSoup(snippet_new, "lxml")

            index_doc = cat_label.lower()

            # get existing cat-index HTML
            if not Path(f"./{WIKI_DIR}/{index_doc}.html").exists():
                # cat-event HTML file does not exist. let's build it from scratch
                # and write it to disk w/o doing the HTML-swap step
                # (as unnecessary at this point).
                cat_index = await make_category_index(cat)
                filepath = f"{cat_index['slug']}"
                await write_to_disk(filepath, cat_index["html"], sem=None)

                break

            index_old = Path(f"./{WIKI_DIR}/{index_doc}.html").read_text()

            # find cat index's list item (article snippet) matching
            # against given article's slug
            soup = BeautifulSoup(index_old, "lxml")

            # replace matched article snippet with newer one
            article_snippet = soup.select(f"#{article['slug']}")
            if len(article_snippet) > 0:
                for item in article_snippet:
                    item.replace_with(snippet_new)

                # write updated cat-index HTML back to disk
                cat_html = str(soup.prettify())
                task = write_to_disk(index_doc, cat_html, sem=None)
                cat_tasks_html.append(asyncio.ensure_future(task))

            else:
                # if no matching from the old snippet,
                # it means we need to insert the article snippet
                # into the page.
                # do we try to insert the snippet in the correct position
                # in the cat index list? no, we just rebuild the entire
                # page. easier and more effective than otherwise having to
                # compare against all the other article snippets and find
                # in which position the newly created or restored
                # article snippet should be inserted.

                cat_index = await make_category_index(cat)
                filepath = f"{cat_index['slug']}"
                await write_to_disk(filepath, cat_index["html"], sem=None)

                break

    await asyncio.gather(*cat_tasks_html)
