from dotenv import load_dotenv
import os
import tomli
import httpx
from fetch import query_continue, create_context, fetch_article
import asyncio
import time
from templates import get_template, make_event_index
from build_article import make_article, save_article
import json
from slugify import slugify
from copy_assets import main as copy_assets
load_dotenv()


async def get_category(URL: str, cat: str):

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

    context = create_context(ENV)
    async with httpx.AsyncClient(verify=context) as client:
        data = {cat: []}
        async for response in query_continue(client, URL, params):

            response = response['categorymembers']
            if len(response) > 0 and 'missing' in response[0]:
                title = response[0]['title']
                print(f"the page could not be found => {title}")
                return False
            
            else:
                data[cat].extend(response)

        return data


async def main(ENV: str, URL: str):
    """
    this function (re-)build the entire wiki by fetching a set of specific
    pages from the MediaWiki instance
    """

    # / summer academies
    # these pages are queried by `Category:Event` and `Type:HDSA<year>`
    # it's not necessary to fetch the Type info now, as we are going to fetch
    # each page in the list on its own, therefore upon mapping over Event pages
    # we can "manually" pick them apart by `Type:HDSA<year>`

    with open("settings.toml", mode="rb") as f:
        config = tomli.load(f)

    cats = config['wiki']['categories']
    indexes = config['wiki']['indexes']

    cat_tasks = []
    for cat in cats:
        task = get_category(URL, cat)
        cat_tasks.append(asyncio.ensure_future(task))

    articles = await asyncio.gather(*cat_tasks)

    # print('articles =>', json.dumps(articles, indent=4))

    # flat nested list
    # articles = [article for subarticle in articles for article in subarticle]

    # template = get_template('article', None)
    context = create_context(ENV)
    timeout = httpx.Timeout(10.0, connect=60.0)

    # add semaphore as when running
    # save_article => write_file_to_disk
    # we might get back an error like "too many files open"
    # https://github.com/Tinche/aiofiles/issues/83#issuecomment-761208062
    sem = asyncio.Semaphore(int(os.getenv('SEMAPHORE')))

    async with httpx.AsyncClient(verify=context, timeout=timeout) as client:

        for category in articles:
            cat = list(category.keys())[0]
            template = get_template(cat, None)

            # process single article
            art_tasks = []
            for k, v in category.items():
                # make_article first fetches the article and handles
                # in case nothing valid is returned
                # we want that info too

                # pass list of articles to Event page
                # to figure out what's needed
                # print('ccc =>', [cat, indexes])
                # if cat in indexes:
                #     await make_index(v, cat, client)

                # return

                for article in v:
                    metadata_only = True
                    task = make_article(article['title'], client, metadata_only)
                    art_tasks.append(asyncio.ensure_future(task))

            prepared_articles = await asyncio.gather(*art_tasks)
            print(f"articles: {len(prepared_articles)}")

            if metadata_only:
                articles_metadata = prepared_articles

            else:
                articles_html = [item[0] for item in prepared_articles]
                articles_metadata = [item[1] for item in prepared_articles]

            event_index = await make_event_index(articles_metadata, cat)


            copy_assets()
            return

            # save single article
            save_tasks = []
            for article in articles_html:
                task = save_article(article, template, sem)
                save_tasks.append(asyncio.ensure_future(task))

            await asyncio.gather(*save_tasks)
            


    # await make_index(articles)

if __name__ == '__main__':

    ENV = os.getenv('ENV')
    URL = os.getenv('BASE_URL')

    start_time = time.time()

    # -- run everything
    asyncio.run(main(ENV, URL))
    print("--- %s seconds ---" % (time.time() - start_time))
