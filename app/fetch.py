import os
import ssl
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from slugify import slugify

from app.log_to_file import main as log
from app.read_settings import main as read_settings

load_dotenv()


ENV = os.getenv("ENV")
URL = os.getenv("BASE_URL")
MEDIA_DIR = os.getenv("MEDIA_DIR")

config = read_settings()


def create_context(ENV: str | None) -> ssl.SSLContext | bool:
    """
    Helper function to detect whether httpx needs to pass
    a custom TLS certificate (if running in `ENV=dev`), or not.
    """

    if ENV == "dev":
        base_dir = Path(__file__).parent.parent

        context = ssl.create_default_context()
        LOCAL_CA = os.getenv("LOCAL_CA")
        context.load_verify_locations(cafile=f"{base_dir}/{LOCAL_CA}")

        return context

    else:
        # True use default CA bundle
        return True


async def query_continue(client, url: str | None, params: dict[str, str]):
    """
    Helper function needed by MediaWiki's APIs to fetch all the data
    from a given `list` endpoint (eg. category). The code paginates
    through the entire list until all results are returned.

    Refs:
    - <https://www.mediawiki.org/wiki/API:Continue#Example_3:_Python_code_for_iterating_through_all_results>
    - <https://github.com/nyurik/pywikiapi/blob/master/pywikiapi/Site.py#L259>
    """

    request = params
    last_continue = {}

    while True:
        req = request.copy()
        req.update(last_continue)

        try:
            response = await client.get(url, params=req)
            result = response.json()

            if "warnings" in result:
                print(result["warnings"])
            if "query" in result:
                yield result["query"]
            if "continue" not in result:
                # print('query-continue over, break!')
                break

            last_continue = result["continue"]

        except httpx.TimeoutException:
            await log("error", f"query-continue e => {params}\n", sem=None)


async def fetch_article(title: str, client):
    """
    Fetch an article by its title, running several requests
    to get all the necessary bits of data.
    """

    print(f"fetching article {title}")

    # for HTML-parsed wiki article
    parse_params = {
        "action": "parse",
        "prop": "text|langlinks|categories|templates|images|displaytitle",
        "page": title,
        "formatversion": "2",
        "format": "json",
        "redirects": "1",
        "disableeditsection": "1",
        "disablestylededuplication": "1",
    }

    # for wiki article's  oldest revisions and backlinks fields
    query_params = {
        "action": "query",
        "titles": title,
        "prop": "revisions",
        "rvdir": "newer",
        "rvprop": "timestamp",
        "bltitle": title,
        "list": "backlinks",
        "formatversion": "2",
        "format": "json",
        "redirects": "1",
    }

    # we might either want to fetch the whole list of revisions in several
    # HTTP calls, (see for instance fetch_category()), or do two HTTP calls
    # and fetch the first 5 + the last one in the list. we do this second
    # option given MW's APIs are what they are...
    rev_params = {
        "action": "query",
        "titles": title,
        "prop": "revisions",
        "rvdir": "older",
        "rvprop": "timestamp",
        "formatversion": "2",
        "format": "json",
        "redirects": "1",
    }

    article = None
    backlinks = None
    redirect_target = None

    try:
        parse_response = await client.get(URL, params=parse_params)
        parse_data = parse_response.json()
        parse_response.raise_for_status()

        query_response = await client.get(URL, params=query_params)
        query_data = query_response.json()
        query_response.raise_for_status()

        rev_response = await client.get(URL, params=rev_params)
        rev_data = rev_response.json()
        rev_response.raise_for_status()

        query_data = query_data["query"]
        rev_data = rev_data["query"]

        # -- ns: -1 is part of Special Pages, we don't parse those
        if query_data["pages"][0]["ns"] == -1:
            return article, backlinks, redirect_target

        if "parse" in parse_data:

            # # -- filter out `Concept:<title>` articles
            # if parse_data['parse']['title'].startswith("Concept:"):
            #     return article, backlinks, redirect_target

            # # -- filter out `Special:<title>` articles
            # if parse_data['parse']['title'].startswith("Special:"):
            #     return article, backlinks, redirect_target

            # -- filter out `<title>/<num-version>/<lang>
            # (eg article snippet translation)

            article = parse_data["parse"]

            rev_beginning = query_data["pages"][0]["revisions"]
            rev_end = rev_data["pages"][0]["revisions"]

            article["creation"] = rev_beginning[0]["timestamp"]
            article["last_modified"] = rev_end[0]["timestamp"]

            backlinks = query_data["backlinks"]

            for link in backlinks:
                link["slug"] = slugify(link["title"])

            if article and len(article["redirects"]) > 0:
                redirect_target = article["redirects"][0]["to"]

        return article, backlinks, redirect_target

    except httpx.HTTPError as exc:
        await log(
            "error",
            "(fetch) get-article err :: HTTP Exception for"
            f"{exc.request.url} - {exc}\n",
            sem=None,
        )

        return article, backlinks, redirect_target


async def fetch_category(cat: str, client) -> list[dict[str, bool | dict[str, int]]]:
    """
    Fetch all the articles from the given cat.
    """

    print(f"fetching category data {cat}")

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

    # -- get full list of entries from category
    data = []
    async for response in query_continue(client, URL, params):

        response = response["categorymembers"]
        if len(response) > 0 and "missing" in response[0]:
            title = response[0]["title"]
            print(f"the page could not be found => {title}")

        else:
            data.extend(response)

    return data


async def query_wiki(
    ENV: str | None, URL: str | None, query: str
) -> list[dict[Any, Any]] | bool:
    """
    Run a search query to MediaWiki and return its results.
    """

    print(f"Querying mediawiki for { query } ...")

    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "formatversion": "2",
        "format": "json",
        "redirects": "1",
    }

    context = create_context(ENV)
    timeout = httpx.Timeout(10.0, connect=60.0)
    results = []
    async with httpx.AsyncClient(verify=context, timeout=timeout) as client:
        async for response in query_continue(client, URL, params):
            response = response["search"]
            if len(response) > 0 and "missing" in response[0]:
                title = response[0]["title"]
                print(f"the page could not be found => {title}")
                return False
            else:
                results.extend(response)

    return results


def convert_article_trans_title_to_regular_title(title: str) -> str:
    """
    Extract given title from a translation-like format to
    a normal, title-only, format.

    Check if article is a snippet translation, either of:
    - <title>/<Page display title>/<lang>
    - <title>/<num-version>/<lang>

    And convert Title to regular article title
    like `<title>/<lang>` so we can update it, instead of
    ignoring the translation snippet.
    """

    translation_langs = [
        config["wiki"]["default"],
        config["wiki"]["translation_langs"][0],
    ]

    lang_stem = title.split("/")[-1]

    # remove `Traslations:` prefix
    title = title.split("Translations:")[-1]

    # check if value before lang is a number
    tokens = title.split("/")
    if len(tokens) >= 2:
        
        # `Page display title` is used for the article title translation:
        # though we might not use it, let's add it as a check,
        # so if we change that field the code does not break.

        if tokens[-2] == "Page display title" or tokens[-2].isdigit():

            # check if article's title ending is matching any of the lang set in
            # the settings.toml variable `translation_langs`
            # and return just actual title without lang and id tokens
            if lang_stem in translation_langs:
                t = tokens[:-2]
                t.append(lang_stem)

                return "/".join(t)

    # if not matching translation title, return as it is
    return title
