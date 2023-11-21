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
from app.build_article import make_article


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

        # -- make pagination
        pagination = paginator(data, 50, page)

        metadata_only = True
        art_tasks = []
        for article in pagination['data']:
            task = make_article(article['title'], client, metadata_only)
            art_tasks.append(asyncio.ensure_future(task))

        prepared_articles = await asyncio.gather(*art_tasks)

        article = None
        save_to_disk = False
        sorting = None

        print(f"make-cat-index template => {cat_label}")

        if cat_label == 'Events':
            print(f"pagination => {pagination}")
            article = await make_event_index(prepared_articles,
                                             cat_key,
                                             cat_label,
                                             save_to_disk,
                                             pagination,
                                             sorting)

        elif cat_label == 'Collaborators':
            article = await make_collaborators_index(prepared_articles, cat, cat_label)

        elif cat_label == 'Publishing':
            article = await make_publishing_index(prepared_articles, cat, cat_label, save_to_disk)

        elif cat_label == 'Tools':
            article = await make_tool_index(prepared_articles, cat, cat_label, save_to_disk, sorting)

        elif cat_label == 'Articles':
            article = await make_article_index(prepared_articles, cat, cat_label)


        if article:
            import json
            print(f"build-cat-index (return article) :: {cat_key} => {json.dumps(article, indent=4)}")
            return (article)
