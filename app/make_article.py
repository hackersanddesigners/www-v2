from fetch import article_exists, fetch_article
from parser import parser
from slugify import slugify


async def make_article(page_title: str, client):

    if not article_exists(page_title, client):
        # TODO handle article remove from local wiki
        print('article not found! it could have been deleted and we got notified about it')

    else:
        article = await fetch_article(page_title, client)
        body_html = await parser(article)

        return {
            "title": page_title,
            "html": body_html,
            "slug": slugify(page_title)
           }
