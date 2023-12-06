import os
import asyncio
from app.fetch import (
    create_context,
    query_continue,
)
import httpx
from app.views.template_utils import (
    paginator,
)
from .views.views import (
    make_event_index,
    make_collaborators_index,
    make_publishing_index,
    make_tool_index,
    make_article_index,
)
from app.read_settings import main as read_settings
from app.build_article import (
    make_article,
    save_article,
)


ENV = os.getenv('ENV')
URL = os.getenv('BASE_URL')
config = read_settings()


async def make_category_index(cat: str, page: int | None = 0) -> str:
    """
    """

    print(f"make-cat-index => {cat, page}")

    cat_key = None
    cat_label = None

    cats = config['wiki']['categories']

    for k, v in cats.items():
        if k.lower() == cat:
            cat_key = k
            cat_label = cats[k]['label']


    if not cat_key:
        return

    # --

    params = {
        'action': 'query',
        'list': 'categorymembers',
        'cmtitle': f"Category:{cat_key}",
        'cmlimit': '50',
        'cmprop': 'ids|title|timestamp',
        'formatversion': '2',
        'format': 'json',
        'redirects': '1',
    }

    context = create_context(ENV)
    timeout = httpx.Timeout(10.0, connect=60.0)
    async with httpx.AsyncClient(verify=context) as client:

        # -- get full list of entries from category
        data = []
        async for response in query_continue(client, URL, params):

            response = response['categorymembers']
            if len(response) > 0 and 'missing' in response[0]:
                title = response[0]['title']
                print(f"the page could not be found => {title}")

            else:
                data.extend(response)


        metadata_only = True
        art_tasks = []
        for article in data:
            task = make_article(article['title'], client, metadata_only)
            art_tasks.append(asyncio.ensure_future(task))

        prepared_articles = await asyncio.gather(*art_tasks)

        article = None
        sorting = None

        if cat_label == 'Events':
            article = await make_event_index(prepared_articles, cat_key, cat_label, sorting)

        elif cat_label == 'Collaborators':
            article = await make_collaborators_index(prepared_articles, cat_key, cat_label)

        elif cat_label == 'Publishing':
            article = await make_publishing_index(prepared_articles, cat_key, cat_label)

        elif cat_label == 'Tools':
            article = await make_tool_index(prepared_articles, cat_key, cat_label, sorting)

        elif cat_label == 'Articles':
            article = await make_article_index(prepared_articles, cat_key, cat_label)


        if article:
            return (article)


async def update_categories(categories: list[str], template, sem):
    """
    """

    cat_tasks = []
    for cat in categories:
        task = make_category_index(cat)
        cat_tasks.append(asyncio.ensure_future(task))

    prepared_category_indexes = await asyncio.gather(*cat_tasks)
    prepared_category_indexes = [item for item
                                 in prepared_category_indexes
                                 if item is not None]

    cat_tasks_html = []
    for cat_index in prepared_category_indexes:
        filepath = f"{cat_index['slug']}"
        task = save_article(cat_index, filepath, template, sem)
        cat_tasks_html.append(asyncio.ensure_future(task))
        
    await asyncio.gather(*cat_tasks_html)
