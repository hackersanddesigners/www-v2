from dotenv import load_dotenv
import os
import tomli

import httpx
from pathlib import Path

from requests_helper import query_continue, create_context
import asyncio

from save_article import save_article
from templates import make_index
load_dotenv()


ENV = os.getenv('ENV')
URL = os.getenv('BASE_URL')


async def main():
    """
    this function (re-)build the entire wiki by fetching a set of specific
    pages from the MediaWiki instance
    """

async def get_category(cat: str):

    params = {
        'action': 'query',
        'list': 'categorymembers',
        'cmtitle': f"Category:{cat}",
        'cmlimit': '50',
        'cmprop': 'ids|title|timestamp',
        # 'cmsort': 'timestamp',
        # 'cmdir': 'asc',
        'formatversion': '2',
        'format': 'json',
        'redirects': '1',
    }

    context = create_context(ENV)
    async with httpx.AsyncClient(verify=context) as client:
        data = []
        async for response in query_continue(client, URL, params):

            cat = response['categorymembers']
            if len(cat) > 0 and 'missing' in cat[0]:
                title = cat[0]['title']
                print(f"the page could not be found => {title}")
                return False
            
            else:
                data.extend(cat)

        return data

    # TODO would be nice to start a request Session and
    # then loop over each category as "one" operation

    # / summer academies
    # these pages are queried by `Category:Event` and `Type:HDSA<year>`
    # it's not necessary to fetch the Type info now, as we are going to fetch
    # each page in the list on its own, therefore upon mapping over Event pages
    # we can "manually" pick them apart by Type:HDSA<year>

    with open("settings.toml", mode="rb") as fp:
        config = tomli.load(fp)

    cats = config['wiki']['categories']

    articles = []
    for cat in cats:
        results = await get_category(cat)
        articles.extend(results)
        print(f"cat:{cat} => {len(results)}")

    if ENV == 'dev':
        base_dir = Path(__file__).parent.parent
        import ssl
        context = ssl.create_default_context()
        LOCAL_CA = os.getenv('LOCAL_CA')
        context.load_verify_locations(cafile=f"{base_dir}/{LOCAL_CA}")

        async with httpx.AsyncClient(verify=context) as client:
            for article in articles:
                await save_article(article['title'], client)

    make_index(articles)
    await make_index(articles)

# -- run everything
asyncio.run(main())

# if __name__ == 'main':
#     asyncio.run(main())
