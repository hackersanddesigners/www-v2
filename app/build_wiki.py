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
    make_index_sections,
    make_front_index,
    make_sitemap
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


async def main(ENV: str, URL: str, metadata_only: bool):
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

        articles_metadata_index = []

        for category in articles:
            cat = list(category.keys())[0]
            cat_label = cats[cat]['label']

            filters = {
                'slug': make_url_slug,
                'ts': make_timestamp,
            }
            template = get_template(cat, filters)

            # process single article
            art_tasks = []
            for k, v in category.items():
                for article in v:
                    task = make_article(article['title'], client, metadata_only)
                    art_tasks.append(asyncio.ensure_future(task))

            prepared_articles = await asyncio.gather(*art_tasks)
            print(f"articles: {len(prepared_articles)}")

            if metadata_only:
                articles_metadata = prepared_articles
                articles_metadata_index.extend(articles_metadata)

            else:

                # check for any article translation present as backlink in prepared_articles,
                # fetch it and add it to the list of articles to write to disk (article_list)

                # do we really need to do a second pass like this to fetch any translated
                # article and add it to the prepated_articles list, and then loop
                # over that list again and again?
                for item in prepared_articles:
                    if item is not None:
                        trans_tasks = []
                        if len(item[1]['translations']) > 0:
                            for translation in item[1]['translations']:
                                trans_task = make_article(translation, client, metadata_only)
                                trans_tasks.append(asyncio.ensure_future(trans_task))

                            t_articles = await asyncio.gather(*trans_tasks)
                            article_list.extend(prepared_articles)

                        
                articles_metadata = [item[1] for item in prepared_articles if item is not None]
                articles_metadata_index.extend(articles_metadata)

                articles_html = [item[0] for item in prepared_articles if item is not None]

                # save single article
                save_tasks = []
                for idx, article in enumerate(articles_html):
                    article_metadata = articles_metadata[idx]
                    filepath = f"{article['slug']}"

                    task = save_article(article, filepath, template, sem)
                    save_tasks.append(asyncio.ensure_future(task))

                    await asyncio.gather(*save_tasks)


            # -- create index sections
            # TODO how does this fit with the web-server routing setup?
            await make_index_sections(articles_metadata, cat, cat_label)
            
        # -- make front-page
        await make_front_index(config['wiki']['frontpage'])

        # any useful?
        await make_sitemap(articles_metadata_index)

        # -- ahah
        copy_assets()            


if __name__ == '__main__':

    ENV = os.getenv('ENV')
    URL = os.getenv('BASE_URL')

    if len(argv) < 2:
        metadata_only = False
    elif argv[1].lower() == 'true':
        metadata_only = True


    start_time = time.time()

    # -- run everything
    asyncio.run(main(ENV, URL, metadata_only))
    print("--- %s seconds ---" % (time.time() - start_time))
        
