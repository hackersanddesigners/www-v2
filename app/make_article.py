from fetch import article_exists, fetch_article
from parser import parser
from slugify import slugify


def make_article(page_title: str):

    if not article_exists(page_title):
        # TODO handle article remove from local wiki
        print('article not found! it could have been deleted and we got notified about it')

    else:
        article = fetch_article(page_title)
        body_html = parser(article)

        return {
            "title": page_title,
            "html": body_html,
            "slug": slugify(page_title)
           }
