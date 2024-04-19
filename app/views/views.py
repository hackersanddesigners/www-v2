import asyncio
import json
import os
from typing import Collection, Sequence

import aiofiles
import arrow
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from slugify import slugify

from app.build_article import make_article, make_footer_nav, make_nav
from app.fetch import create_context, fetch_category
from app.file_ops import file_lookup
from app.log_to_file import main as log
from app.read_settings import main as read_settings

from .template_utils import extract_datetime, get_template, ts_pad_hour

load_dotenv()


# -- front-page


async def make_front_index(
    home_art: str, home_cat: str
) -> dict[str, bool | dict[str, int]]:
    """
    Prepare necessary data for the Front index page.
    """

    config = read_settings()
    langs = config["wiki"]["langs"]

    ENV = os.getenv("ENV")
    context = create_context(ENV)
    timeout = httpx.Timeout(10.0, connect=60.0)
    async with httpx.AsyncClient(verify=context, timeout=timeout) as client:

        # list of articles w/ `highlight` cat
        data = await fetch_category(home_cat, client)
        art_tasks = []
        for article in data:
            title = article["title"]
            # filter away translations
            lang_stem = title.split("/")[-1]
            if lang_stem not in langs:
                task = make_article(article["title"], client)
                art_tasks.append(asyncio.ensure_future(task))

        highlight_articles = await asyncio.gather(*art_tasks)
        highlight_articles = [item for item in highlight_articles if item is not None]

        # `Hackers & Designers` article
        article = await make_article(home_art, client)
        article["slug"] = "index"
        article["last_modified"] = article["metadata"]["last_modified"]
        article["backlinks"] = article["metadata"]["backlinks"]

        # add highlights to dict
        article["highlights"] = highlight_articles

        # -- upcoming events
        event_filename = slugify(config["wiki"]["categories"]["Event"]["label"])

        upcoming_events = []
        upcoming_events_str = []
        events_path = file_lookup(event_filename)
        current_timestamp = arrow.now().to("local")

        if len(events_path) > 0:
            async with aiofiles.open(events_path[0], mode="r") as f:
                tree = await f.read()
                soup = BeautifulSoup(tree, "lxml")

                upcoming_events = soup.find_all("li", {"class": "when-upcoming"})

                for event in upcoming_events:
                    # check if upcoming-event's date is bigger than
                    # current timestamp. this helps to keep the list of
                    # upcoming events even when no change is done to an event
                    # and by consequence to the events page, which we
                    # use above to query for all the upcoming events.

                    event_date = arrow.get(event.attrs["data-start"])

                    if event_date > current_timestamp:
                        upcoming_events_str.append(
                            {
                                "date": event_date,
                                "html": str(event),
                            }
                        )

                # sort event by ASC order using the `date` key
                upcoming_events_str = sorted(
                    upcoming_events_str, key=lambda e: e["date"]
                )

                # make new list keeping only the html of each event and get rid of the date key
                article["upcoming"] = [event["html"] for event in upcoming_events_str]

                return article

        else:
            print(f"make-frontindex err => {events_path} does not exist in the wiki.")


# -- events


def make_article_event(
    article: dict[str, list[str] | list[dict[str, str]]]
) -> dict[str, list[str] | list[dict[str, str]]]:
    """
    Extend necessary data for the Event article.
    """

    date = None
    time = None

    date_now = arrow.now()

    if "date" in article["metadata"]["parsed_metadata"]:
        date = extract_datetime(article["metadata"]["parsed_metadata"]["date"])

    if "time" in article["metadata"]:
        time = extract_datetime(article["metadata"]["parsed_metadata"]["time"])

    article_ts = {"start": None, "end": None}

    if date is not None and time is not None:

        tokens_start = time[0].split(":")
        ts_start = ts_pad_hour(tokens_start)

        if len(time) > 1:
            tokens_end = time[1].split(":")
            ts_end = ts_pad_hour(tokens_end)

            article["metadata"]["parsed_metadata"]["time"] = f"{ts_start}-{ts_end}"

        else:
            article["metadata"]["parsed_metadata"]["time"] = f"{ts_start}"

        # -- construct datetime start
        date_start = date[0]

        dts_start = f"{date_start} {ts_start}"
        article_ts["start"] = arrow.get(dts_start, "YYYY/MM/DD HH:mm")

        if len(date) > 1:
            # -- construct datetime end
            date_end = date[1]

            dts_end = f"{date_end} {ts_end}"
            article_ts["end"] = arrow.get(dts_end, "YYYY/MM/DD HH:mm")

    elif date is not None:
        date_start = date[0]

        dts_start = f"{date_start}"
        article_ts["start"] = arrow.get(dts_start, "YYYY/MM/DD")

        if len(date) > 1:
            date_end = date[1]

            dts_end = f"{date_end}"
            article_ts["end"] = arrow.get(dts_end, "YYYY/MM/DD")

    if article_ts["start"] is not None and article_ts["end"] is not None:

        if date_now > article_ts["start"] and date_now < article_ts["end"]:
            article["metadata"]["when"] = "happening"

    if article_ts["start"]:

        if date_now < article_ts["start"]:
            article["metadata"]["when"] = "upcoming"

        else:
            article["metadata"]["when"] = "past"

    # -- prepare article dates for template

    article["metadata"]["dates"] = {"start": None, "end": None}
    article["metadata"]["times"] = {"start": None, "end": None}

    if article_ts["start"] is not None:
        article["metadata"]["dates"]["start"] = arrow.get(article_ts["start"]).format(
            "YYYY-MM-DD"
        )
        article["metadata"]["times"]["start"] = arrow.get(article_ts["start"]).format(
            "HH:mm"
        )
    else:
        article["metadata"]["dates"]["start"] = None
        article["metadata"]["times"]["start"] = None

    if article_ts["end"] is not None:
        article["metadata"]["dates"]["end"] = arrow.get(article_ts["end"]).format(
            "YYYY-MM-DD"
        )
        article["metadata"]["times"]["end"] = arrow.get(article_ts["end"]).format(
            "HH:mm"
        )
    else:
        article["metadata"]["dates"]["end"] = None
        article["metadata"]["times"]["end"] = None

    return article


async def make_event_index(
    articles: list[dict[str, list[str] | list[dict[str, str]]] | None],
    cat: str,
    cat_label: str,
) -> dict[str, list[str] | list[dict[str, str]]]:
    """
    Prepare necessary data for the Event index page.
    """

    template = get_template(f"{cat}-index")

    # events
    # - upcoming
    # - happening right now
    # - past
    #
    # order articles by date desc

    events = []
    types = []

    for article in articles:
        if article:

            prepared_article = make_article_event(article)

            if (
                prepared_article["metadata"]
                and prepared_article["metadata"]["parsed_metadata"]
                and prepared_article["metadata"]["parsed_metadata"]["type"]
            ):

                event_type = prepared_article["metadata"]["parsed_metadata"]["type"]
                if event_type and event_type not in types:
                    types.append(event_type)

            events.append(article)

    # -- sorting events by date desc
    events = sorted(
        events, key=lambda d: d["metadata"]["dates"]["start"] or "", reverse=True
    )
    await log("info", f"make-event => un-filtered {len(events)}\n", sem=None)

    await log("info", f"make-event => filtered {len(events)}\n", sem=None)

    types = sorted(types, key=str.lower)

    nav = make_nav()
    footer_nav = make_footer_nav()

    article_index = {
        "title": cat,
        "slug": slugify(cat_label),
        "events": events,
        "types": types,
        "nav": nav,
        "footer_nav": footer_nav,
        "html": "",
    }

    document = template.render(article=article_index)
    article_index["html"] = document

    return article_index


# -- collaborators


async def make_collaborators_index(
    articles: list[dict[str, list[str] | list[dict[str, str]]]],
    cat: str,
    cat_label: str,
) -> dict[str, list[str] | list[dict[str, str]]]:
    """
    Prepare necessary data for the Collaborators index page.
    """

    template = get_template(f"{cat}-index")

    # collaborators
    # list of names w/ connected projects / articles?
    # similar to MediaWiki syntax
    # {{Special:WhatLinksHere/<page title>}}

    nav = make_nav()
    footer_nav = make_footer_nav()

    articles = sorted(articles, key=lambda d: d["metadata"]["creation"], reverse=True)

    article = {
        "title": cat,
        "slug": slugify(cat_label),
        "collaborators": articles,
        "nav": nav,
        "footer_nav": footer_nav,
        "html": "",
    }

    document = template.render(article=article)
    article["html"] = document

    return article


# -- publishing


async def make_publishing_index(
    articles: list[dict[str, list[str] | list[dict[str, str]]]],
    cat: str,
    cat_label: str,
) -> dict[str, list[str] | list[dict[str, str]]]:
    """
    Prepare necessary data for the Publishing index page.
    """

    template = get_template(f"{cat}-index")
    nav = make_nav()
    footer_nav = make_footer_nav()

    articles = sorted(articles, key=lambda d: d["metadata"]["creation"], reverse=True)

    article = {
        "title": cat,
        "slug": slugify(cat_label),
        "articles": articles,
        "footer_nav": footer_nav,
        "nav": nav,
        "html": "",
    }

    document = template.render(article=article)
    article["html"] = document

    return article


# -- tool


async def make_tool_index(
    articles: list[dict[str, list[str] | list[dict[str, str]]]],
    cat: str,
    cat_label: str,
) -> dict[str, Sequence[Collection[str]]]:
    """
    Prepare necessary data for the Tool index page.
    """

    template = get_template(f"{cat}-index")
    nav = make_nav()
    footer_nav = make_footer_nav()

    articles = sorted(articles, key=lambda d: d["metadata"]["creation"], reverse=True)

    article = {
        "title": cat_label,
        "slug": slugify(cat_label),
        "articles": articles,
        "nav": nav,
        "footer_nav": footer_nav,
        "html": "",
    }

    # print( json.dumps( article, indent=2 ) )

    document = template.render(article=article)
    article["html"] = document

    return article


# -- search


async def make_search_index(
    articles: list[dict[str, list[str] | list[dict[str, str]]]], query: str
) -> dict[str, Sequence[Collection[str]]]:
    """
    Prepare necessary data for the Search index page.
    """

    nav = make_nav()
    footer_nav = make_footer_nav()

    for result in articles:
        print(json.dumps(result, indent=2))
        result["slug"] = slugify(result["title"])

    article = {
        "title": '"' + query + '" search results',
        "slug": "search",
        "query": query,
        "results": articles,
        "footer_nav": footer_nav,
        "nav": nav,
    }

    return article


# -- error


async def make_error_page(status_code, message: str):
    """
    Prepare necessary data for error page
    """
    nav = make_nav()
    footer_nav = make_footer_nav()
    article = {
        "title": "Error",
        "slug": "error",
        "error": status_code,
        "message": message,
        "footer_nav": footer_nav,
        "nav": nav,
    }
    return article


# -- article


async def make_article_index(
    articles: list[dict[str, list[str] | list[dict[str, str]]]],
    cat: str,
    cat_label: str,
) -> dict[str, Sequence[Collection[str]]]:
    """
    Prepare necessary data for the Article index page.
    """

    template = get_template(f"{cat}-index")

    nav = make_nav()
    footer_nav = make_footer_nav()

    article = {
        "title": cat,
        "slug": slugify(cat_label),
        "articles": articles,
        "nav": nav,
        "footer_nav": footer_nav,
        "html": "",
    }

    document = template.render(article=article)
    article["html"] = document

    return article
