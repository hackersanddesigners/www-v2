import os
import asyncio
from app.fetch import fetch_article
from app.parser import parser
from bs4 import BeautifulSoup
from slugify import slugify
import aiofiles
from aiofiles import os as aos
from app.views.template_utils import (
    make_url_slug,
    make_mw_url_slug,
    make_timestamp,
    make_timestamp_full,
)
from pathlib import Path
from app.read_settings import main as read_settings
from app.file_ops import (
    file_lookup,
    write_to_disk,
    search_file_content,
)


WIKI_DIR = Path(os.getenv('WIKI_DIR'))
config = read_settings()
mw_host = config['domain']['mw_url']

def make_nav():
    """
    make a list of dictionaries {label, uri} as links
    to listed categories in settings.toml
    """

    cats = config['wiki']['categories']

    nav = []
    for k, v in cats.items():
        if v['nav']:
            label = v['label']
            if 'actual_label' in v:
                label = v['actual_label']
            nav.append({ "label": label,
                      "uri": f"/{slugify(v['label'])}" })

    nav.extend([{
        "label": "About",
        "uri": "About.html"
    },{
    "label": "Contact",
        "uri": "Contact.html"
    }])

    return nav


def make_footer_nav():
    """
    make a sub nav from settings.toml for footer links
    """

    links = config['wiki']['footer_links']

    footer_nav = []
    for k, v in links.items():
        if v['nav']:
            footer_nav.append({ "label": v['label'],
                      "uri": f"/{slugify(v['label'])}" })

    return footer_nav


def get_article_field(field: str, article: dict[str]):

    if field in article:
        article_field = article[field]

        if field == 'templates':
            if len(article_field) > 0:
                template = article_field[0]['title'].split(':')[-1]
                return template
        else:
            return article_field

    else:
        return None


def get_translations(page_title: str, backlinks: list[str]) -> list[str]:
    """
    Return list of URLs pointing to translations of the given article.
    """

    translations = config['wiki']['translation_langs']
    matches = [f"{page_title}/{lang}" for lang in translations]

    return [page['title'] for page in backlinks
            if page['title'] in matches]


def update_backlink(backlink, new_title):
    """
    Update given backlink to new article title.
    """
   
    new_url = None

    # update MW-style URL w/ possible querystring
    if 'index.php?' in backlink.attrs['href']:
        new_title_slug = make_mw_url_slug(new_title)
        new_url = mw_host + '/index.php?title=' + new_title_slug
                        
        query_tokens = backlink.attrs['href'].split('&')
        if len(query_tokens) > 1:
            new_url = f"{new_url}&{query_tokens[-1]}"
                            
            backlink.attrs['href'] = new_url

    # update kebab-style URL
    else:
        new_url = f"/{slugify(new_title)}.html"
        backlink.attrs['href'] = new_url
        backlink.string = new_title
    
    print(f"backlink new-url => {new_url}")
    

def remove_backlink(backlink):
    """
    Remove given backlink from DOM.
    """

    backlink.decompose()


async def update_backlinks(filepath: str,
                           old_title: str,
                           new_title: str | None = None,
                           operation: str | None = 'update'):
    """
    yaye
    """

    async with aiofiles.open(f"{WIKI_DIR}/{filepath}", mode='r') as f:
        tree = await f.read()
        soup = BeautifulSoup(tree, 'lxml')
            
        backlinks = soup.find_all('a', href=True)
            
        for backlink in backlinks:
            # we try to match any type of URL
            # independently of their slug style, that is:
            # - <article-title>
            # - /<article-title>
            # - /<article-title>.html
            # - http://localhost:8001/index.php?title=<Article_title_ABC>
            # - http://localhost:8001/index.php?title=<Article_title_ABC>&action=history
            # - http://localhost:8001/index.php?title=<Article_title_ABC>b&action=edit
                
            old_title_slug = slugify(old_title)
            backlink_slug = slugify(backlink.attrs['href'])
                
            if old_title_slug in backlink_slug:
                print(f"update-backlink => {filepath} :: {backlink.attrs['href']}")

                if operation == 'update':
                    update_backlink(backlink, new_title)
                        
                elif operation == 'remove':
                    remove_backlink(backlink)

            
        # write updated article to disk
        # if len(soup.contents) > 0:
        #     new_tree = "".join(str(item) for item in soup.body.contents)

        #     # repl

        filename = Path(filepath).stem
        print(f"backlinks-art-update => {filename}")
        # await write_to_disk(filename, new_tree, sem=None)
        await write_to_disk(filename, soup.prettify(), sem=None)



async def update_article_backlinks(old_title: str,
                                   new_title: str,
                                   operation: str | None = 'update'):
    """
    Grep across WIKI_DIR to check if the given article title has
    backlinks in other HTML files and update them to the newest
    version of the article title.

    scan all category index HTML templates
    with bs4 and update / remove any block + link pointing
    to article updated / removed.
    """

    skip_self = f"{slugify(old_title)}.html"
    matches = search_file_content(old_title, skip_self)
    print(f"update_article_backlinks => {matches}")

    if len(matches) > 0:
        save_tasks = []
        for filepath in matches:
            task = update_backlinks(filepath, old_title, new_title, operation)
            save_tasks.append(asyncio.ensure_future(task))
            
        await asyncio.gather(*save_tasks)


async def make_article(page_title: str, client):

    article, backlinks, redirect_target = await fetch_article(page_title, client)

    # TODO we wouldn't need this get_translations func anymore,
    # since the HTML article contains already links to available translations (?)
    article_translations = []
    if backlinks:
        article_translations = get_translations(page_title, backlinks)

    nav = make_nav()
    footer_nav = make_footer_nav()

    mw_slug = make_mw_url_slug( page_title )
    mw_url = mw_host + '/index.php?title=' + mw_slug


    if article is not None:

        body_html, art_metadata, images = await parser(article, redirect_target)

        metadata = {
            "id": article['pageid'],
            "title": article['title'],
            "mw_url": mw_url,
            "mw_history_url": mw_url + '&action=history',
            "mw_edit_url": mw_url + '&action=edit',
            "images": images,
            "template": get_article_field('templates', article),
            "creation": make_timestamp_full( article['creation'] ),
            "last_modified": make_timestamp_full( article['last_modified'] ),
            "backlinks": backlinks,
            "nav": nav,
            "footer_nav": footer_nav,
            "translations": article_translations,
            "parsed_metadata": art_metadata['info'],
            "categories": art_metadata['categories'],
            "tool_repos": art_metadata['repos_index'],
        }

        article = {
            "title": page_title,
            "html": body_html,
            "slug": slugify(page_title),
            "nav": nav,
            "footer_nav": footer_nav,
            "translations": article_translations,
            "metadata": metadata,
        }

        return article

    else:
        print('article not found! it could have been deleted meanwhile\n and we got notified about it')

        # check if there's a copy of article in `wiki/` and
        # if yes, remove it?

        print(f":: article is none (?) => {page_title}")

        try:
            await delete_article(page_title)

        except Exception as e:
            print(f"delete article err => {e}")


async def redirect_article(article_title: str, redirect_target: str):
    """
    """

    p = Path(article_title)
    filename = slugify(str(p.stem))
    paths = file_lookup(filename)

    if len(paths) > 0:
        fn = paths[0]

        if await aos.path.exists(fn):
            async with aiofiles.open(fn, mode='r') as f:
                tree = await f.read()
                soup = BeautifulSoup(tree, 'lxml')

                main_h1 = soup.body.main.h1
                redirect = f"<p>This page has been moved to <a href=\"{slugify(redirect_target)}.html\">{redirect_target}</a>.</p>"

                main_h1.insert_after(redirect)
                output = soup.prettify(formatter=None)

            async with aiofiles.open(fn, mode='w') as f:
                await f.write(output)


            # TODO is this producing `wiki/<article-title>`
            print(f"redirect_article => {fn.parent.stem} + / + {fn.stem}")
            return f"{fn.parent.stem}/{fn.stem}"

        else:
            print(f"redirect-article: {article_title} not found, nothing done")
            return None


async def save_article(article: str | None, filepath: str, template: str, sem: int):

    if article is not None:
        document = template.render(article=article)
        await write_to_disk(filepath, document, sem)


async def delete_article(article_title: str, cat: str | None = None):
    """
    pass article title and remove it from local wiki dir, if it exists.

    let's construct the correct filepath in here
    instead of demanding the requiring function to
    do it; in this way we uniformize what we need it
    and just assume we receive the title of the article
    and potentially its cat; if cat is None we scan the
    WIKI_DIR for a matching filename.
    """

    print(f"delete-article => {article_title, cat}")

    p = Path(article_title)
    filename = slugify(str(p.stem))

    if cat:
        fn = f"{WIKI_DIR}/{cat}/{filename}.html"
    else:
        paths = file_lookup(filename)

        print(f"delete-article => scan for full filepath => {paths}")
        if len(paths) > 0:
            fn = paths[0]
        else:
            print(f"delete-article => scan-dir found no article match for {filename}")
            return

    if await aos.path.exists(fn):
        await aos.remove(fn)
        print(f"delete-article: {article_title} removed")

    else:
        print(f"delete-article: {article_title} not found, nothing done")
