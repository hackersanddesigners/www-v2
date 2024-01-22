from dotenv import load_dotenv
import os
import json
import arrow
import httpx
from pathlib import Path
from slugify import slugify
from app.log_to_file import main as log
from app.read_settings import main as read_settings
load_dotenv()


ENV = os.getenv('ENV')
URL = os.getenv('BASE_URL')
MEDIA_DIR = os.getenv('MEDIA_DIR')

config = read_settings()


def create_context(ENV):
    if ENV == 'dev':
        base_dir = Path(__file__).parent.parent
        import ssl
        context = ssl.create_default_context()
        LOCAL_CA = os.getenv('LOCAL_CA')
        context.load_verify_locations(cafile=f"{base_dir}/{LOCAL_CA}")

        return context

    else:
        # True use default CA bundle
        return True

# refs:
# <https://www.mediawiki.org/wiki/API:Continue#Example_3:_Python_code_for_iterating_through_all_results>
# <https://github.com/nyurik/pywikiapi/blob/master/pywikiapi/Site.py#L259>
async def query_continue(client, url, params):
    request = params
    last_continue = {}

    tasks = []
    while True:
        req = request.copy()
        req.update(last_continue)

        try:
            response = await client.get(url, params=req)
            result = response.json()

            if 'warnings' in result:
                print(result['warnings'])
            if 'query' in result:
                yield result['query']
            if 'continue' not in result:
                # print('query-continue over, break!')
                break

            last_continue = result['continue']

        except httpx.TimeoutException as exception:
            # print(f"query-continue e => {params['titles']}")

            sem = None
            msg = f"query-continue e => {params['titles']}\n"
            await log('error', msg, sem)


async def fetch_article(title: str, client):
    print(f"fetching article {title}...")

    # for HTML-parsed wiki article
    parse_params = {
        'action': 'parse',
        'prop': 'text|langlinks|categories|templates|images',
        'page': title,
        'formatversion': '2',
        'format': 'json',
        'redirects': '1',
        'disableeditsection': '1',
        'disablestylededuplication': '1',
    }

    # for wiki article's revisions and backlinks fields
    query_params = {
        'action': 'query',
        'titles': title,
        'prop': 'revisions',
        'rvdir': 'newer',
        'rvprop': 'timestamp',
        'bltitle': title,
        'list': 'backlinks',
        'formatversion': '2',
        'format': 'json',
        'redirects': '1'
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

        query_data = query_data['query']

        # -- ns: -1 is part of Special Pages, we don't parse those
        if query_data['pages'][0]['ns'] == -1:
            article = None

        if 'parse' in parse_data:
            # -- filter out `Concept:<title>` articles
            if parse_data['parse']['title'].startswith("Concept:"):
                return

            # -- filter out `Special:<title>` articles
            if parse_data['parse']['title'].startswith("Special:"):
                return

            # -- filter out `<title>/<num-version>/<lang> (eg article snippet translation)

            # translation_langs = config['wiki']['translation_langs']
            # lang_stem = parse_data['parse']['title'].split('/')[-1]

            # check if value before lang is a number
            tokens = parse_data['parse']['title'].split('/')
            if len(tokens) >= 2 and tokens[-2].isdigit():
                
                # check if article's title ending is matching any of the lang set in
                # the settings.toml variable `translation_langs`
                if lang_stem in translation_langs:
                    return


            article = parse_data['parse']

            revs = query_data['pages'][0]['revisions']
            article['creation'] = revs[0]['timestamp']
            article['last_modified'] = revs[len(revs) -1]['timestamp']


            backlinks = query_data['backlinks']

            for link in backlinks:
                link['slug'] = slugify(link['title'])

            if article and len(article['redirects']) > 0:
                redirect_target = article['redirects'][0]['to']

        return article, backlinks, redirect_target


    except httpx.HTTPError as exc:
        print(f"get-article err => {exc}")
        return article, backlinks, redirect_target


async def fetch_category(cat, client):
    print(f"fetching category data...")

    params = {
        'action': 'query',
        'list': 'categorymembers',
        'cmtitle': f"Category:{cat}",
        'cmlimit': '50',
        'cmprop': 'ids|title|timestamp',
        'formatversion': '2',
        'format': 'json',
        'redirects': '1',
    }

    # -- get full list of entries from category
    data = []
    async for response in query_continue(client, URL, params):

        response = response['categorymembers']
        if len(response) > 0 and 'missing' in response[0]:
            title = response[0]['title']
            print(f"the page could not be found => {title}")

        else:
            data.extend(response)


    return data


async def query_wiki(ENV: str, URL: str, query: str):
    print(f"Querying mediawiki for { query } ...")

    params = {
        'action': 'query',
        'list': 'search',
        'srsearch': query,
        'formatversion': '2',
        'format': 'json',
        'redirects': '1',
    }

    context = create_context(ENV)
    timeout = httpx.Timeout(10.0, connect=60.0)
    results = []
    async with httpx.AsyncClient(verify=context, timeout=timeout) as client:
        async for response in query_continue(client, URL, params):
            response = response['search']
            if len(response) > 0 and 'missing' in response[0]:
                title = response[0]['title']
                print(f"the page could not be found => {title}")
                return False
            else:
                results.extend(response)

    return results


async def fetch_file(title: str):
    """
    """

    params = {
        'action': 'query',
        'prop': 'imageinfo',
        'iiprop': 'url|timestamp',
        'titles': title,
        'formatversion': '2',
        'format': 'json',
        'redirects': '1'
    }


    data = []
    context = create_context(ENV)
    timeout = httpx.Timeout(10.0, connect=60.0)

    async with httpx.AsyncClient(verify=context, timeout=timeout) as client:
        async for response in query_continue(client, URL, params):

            if 'missing' in response['pages'][0]:
                title = response['pages'][0]['title']

                msg = f"the image could not be found => {title}\n"
                sem = None
                await log('error', msg, sem)

                return (False, "")

            else:
                data.append(response)


    file_last = data[0]['pages'][0]

    return (True, file_last['imageinfo'][0]['url'])
