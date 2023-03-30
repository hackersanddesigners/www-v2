from dotenv import load_dotenv
import os
import tomli
import httpx
from fetch import query_continue, create_context
import asyncio
import time
from jinja2 import Environment, FileSystemLoader
from build_article import make_article, save_article
from templates import make_index
load_dotenv()


ENV = os.getenv('ENV')
URL = os.getenv('BASE_URL')

start_time = time.time()


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


async def main():
    """
    this function (re-)build the entire wiki by fetching a set of specific
    pages from the MediaWiki instance
    """

    # / summer academies
    # these pages are queried by `Category:Event` and `Type:HDSA<year>`
    # it's not necessary to fetch the Type info now, as we are going to fetch
    # each page in the list on its own, therefore upon mapping over Event pages
    # we can "manually" pick them apart by Type:HDSA<year>

    with open("settings.toml", mode="rb") as f:
        config = tomli.load(f)

    cats = config['wiki']['categories']
    cat_tasks = []
    for cat in cats:
        task = get_category(cat)
        cat_tasks.append(asyncio.ensure_future(task))

    articles = await asyncio.gather(*cat_tasks)

    # flat nested list
    articles = [article for subarticle in articles for article in subarticle]

    context = create_context(ENV)
    timeout = httpx.Timeout(10.0, connect=60.0)

    env = Environment(loader=FileSystemLoader('app/templates'), autoescape=True)
    t = env.get_template('article.html')

    async with httpx.AsyncClient(verify=context, timeout=timeout) as client:

        art_tasks = []
        for article in articles:
            task = make_article(article['title'], client)
            art_tasks.append(asyncio.ensure_future(task))

        articles = await asyncio.gather(*art_tasks)
        print(f"articles: {len(articles)}")


        # add semaphore as when running
        # save_article => write_file_to_disk
        # we might get back an error like "too many files open"
        # https://github.com/Tinche/aiofiles/issues/83#issuecomment-761208062
        sem = asyncio.Semaphore(int(os.getenv('SEMAPHORE')))
        save_tasks = []
        for article in articles:
            task = save_article(article, t, sem)
            save_tasks.append(asyncio.ensure_future(task))

        await asyncio.gather(*save_tasks)
            

    await make_index(articles)

# -- run everything
asyncio.run(main())
print("--- %s seconds ---" % (time.time() - start_time))
