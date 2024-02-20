import os
from pathlib import Path
from slugify import slugify
from bs4 import BeautifulSoup
from app.read_settings import main as read_settings
from app.views.views import make_front_index
from app.views.template_utils import (
    get_template
)
from app.build_article import save_article


async def update_front_index(article_title: str, article_cats: list[str] | None):
    """
    check if:
    - article title = settings.wiki.frontpage, else if
    - article_cats is either 'highlight' or 'event'
    
    if so update front index page and write it to disk.
    """

    WIKI_DIR = Path(os.getenv('WIKI_DIR'))
    config = read_settings()

    index_art = config['wiki']['frontpage']['article']
    index_cat = config['wiki']['frontpage']['category']
        
    article = None

    # check title
    if article_title == index_art:
        article = await make_front_index(index_art, index_cat)

    # else check categories
    if article_cats is None:
        # this handles the case where we delete an article
        # and only have access to its title, no categories.
        # therefore we look if either the upcoming events
        # or highlights section match the article-title

        article_html = Path(f"./{WIKI_DIR}/index.html").read_text()
        soup = BeautifulSoup(article_html, 'lxml')

        pattern = slugify(article_title)
        snippets = soup.select(f"#{pattern}")

        if len(snippets) > 0:
            article = await make_front_index(index_art, index_cat)
    
    else:
        for cat in article_cats:
            if cat in ['event', 'highlight']:
                article = await make_front_index(index_art, index_cat)

    # write to disk
    if article is not None:
        template = get_template('index')
        
        filepath = f"{article['slug']}"
        await save_article(article, filepath, template, sem=None)
