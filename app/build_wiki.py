from dotenv import load_dotenv
import os
import tomli

import httpx
from pathlib import Path

from requests_helper import query_continue
import asyncio

from save_article import x as save_article
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
        req_op = {
            'verb': 'GET',
            'url': URL,
            'params': {
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
            },
            'session': False,
            'stream': False
           }

        data = []

        # TODO DRY this code
        if ENV == 'dev':
            base_dir = Path(__file__).parent.parent
            import ssl
            context = ssl.create_default_context()
            LOCAL_CA = os.getenv('LOCAL_CA')
            context.load_verify_locations(cafile=f"{base_dir}/{LOCAL_CA}")

            async with httpx.AsyncClient(verify=context) as client:
                async for response in query_continue(client, req_op, True):
                    x = response['categorymembers']
                    if len(x) > 0 and 'missing' in x[0]:
                        title = x[0]['title']
                        print(f"the page could not be found => {title}")
                        return False

                    else:
                        data.extend(x)

        else:
            with httpx.Client() as client:
                for response in query_continue(client, req_op, ENV):
                    x = response['categorymembers']
                    if len(x) > 0 and 'missing' in x[0]:
                        title = x[0]['title']
                        print(f"the page could not be found => {title}")
                        return False

                    else:
                        data.extend(x)

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

    # for article in articles:
    #     save_article(article['title'])

    make_index(articles)

# -- run everything
asyncio.run(main())

# if __name__ == 'main':
#     main()
