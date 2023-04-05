from fetch import fetch_article
from parser import parser
from slugify import slugify
from write_to_disk import main as write_to_disk
from delete_article import delete_article


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
        print('article not found! it could have been deleted meanwhile and we got notified about it')

        # check if there's a copy of article in `wiki/` and
        # if yes, remove it?

        try:
            await delete_article(page_title)

        except Exception as e:
            print(f"delete article err => {e}")


async def save_article(article: str | None, template, sem):

    if article is not None:
        document = template.render(article=article)
        await write_to_disk(article['slug'], document, sem)
