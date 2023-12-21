from dotenv import load_dotenv
from sys import argv
import os
import httpx
from app.fetch import (
    query_continue,
    create_context,
    fetch_article,
)
import asyncio
import time
from app.views.views import (
    get_template,
    make_front_index,
)
from app.views.template_utils import (
    make_url_slug,
    make_timestamp,
)
from app.build_article import (
    make_article,
    save_article,
)
import json
from slugify import slugify
from app.copy_assets import main as copy_assets
from app.read_settings import main as read_settings
from app.build_category_index import update_categories
load_dotenv()


async def get_category(ENV: str, URL: str, cat: str):

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
    timeout = httpx.Timeout(10.0, connect=60.0)
    async with httpx.AsyncClient(verify=context, timeout=timeout) as client:
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

    config = read_settings()

    cats = config['wiki']['categories']

    cat_tasks = []
    cat_indexes = {}
    for k, v in cats.items():
        if v['parse']:
            task = get_category(ENV, URL, k)
            cat_tasks.append(asyncio.ensure_future(task))

    articles = await asyncio.gather(*cat_tasks)

    context = create_context(ENV)
    timeout = httpx.Timeout(10.0, connect=60.0)

    # add semaphore as when running
    # save_article => write_file_to_disk
    # we might get back an error like "too many files open"
    # https://github.com/Tinche/aiofiles/issues/83#issuecomment-761208062
    sem = asyncio.Semaphore(int(os.getenv('SEMAPHORE')))

    async with httpx.AsyncClient(verify=context, timeout=timeout) as client:

        frontpage = {"news": None, "upcoming_events": []}

        articles_index = []

        for category in articles:
            cat = list(category.keys())[0]
            cat_label = cats[cat]['label']

            template = get_template(cat)

            # process single article
            art_tasks = []
            for k, v in category.items():
                for article in v:
                    task = make_article(article['title'], client)
                    art_tasks.append(asyncio.ensure_future(task))

            prepared_articles = await asyncio.gather(*art_tasks)
            print(f"articles: {len(prepared_articles)}")

            articles = [item for item
                        in prepared_articles
                        if item is not None]
            
            articles_index.extend(articles)

            save_tasks = []
            for article in articles:
                filepath = f"{article['slug']}"

                task = save_article(article, filepath, template, sem)
                save_tasks.append(asyncio.ensure_future(task))


            # write all articles to disk
            await asyncio.gather(*save_tasks)


        # -- update category index
        categories = [k.lower() for k,v in cats.items()]
        await build_categories(categories, template, sem)

        # -- make front-page
        await make_front_index(config['wiki']['frontpage'])

        # -- ahah
        copy_assets()


if __name__ == '__main__':

    ENV = os.getenv('ENV')
    URL = os.getenv('BASE_URL')


    start_time = time.time()

    # -- run everything
    asyncio.run(main(ENV, URL))
    print("--- %s seconds ---" % (time.time() - start_time))
