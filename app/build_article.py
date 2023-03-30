from fetch import fetch_article
from parser import parser
from slugify import slugify
from write_to_disk import main as write_to_disk


async def make_article(page_title: str, client):

    article = await fetch_article(page_title, client)

    if article is not None:
        body_html = await parser(article)

        return {
            "title": page_title,
            "html": body_html,
            "slug": slugify(page_title)
        }

    else:
        # TODO handle article remove from local wiki
        print('article not found! it could have been deleted and we got notified about it')

        return article


async def save_article(article: str | None, t, sem):

    if article is not None:
        document = t.render(article=article)
        await write_to_disk(article['slug'], document, sem)
