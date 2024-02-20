import os
import asyncio
import httpx
from app.fetch import (
    query_continue,
    create_context,
    fetch_article,
)
from app.parser import parser
from bs4 import BeautifulSoup, Tag
import re
from slugify import slugify
import aiofiles
from aiofiles import os as aos
from app.views.template_utils import (
    get_template,
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


async def make_article(page_title: str, client):

    article, backlinks, redirect_target = await fetch_article(page_title, client)

    # TODO we wouldn't need this get_translations func anymore,
    # since the HTML article contains alreasy links to available translations (?)
    article_translations = []
    if backlinks:
        article_translations = get_translations(page_title, backlinks)

    nav = make_nav()
    footer_nav = make_footer_nav()

    mw_slug = make_mw_url_slug( page_title )
    mw_url = mw_host + '/index.php?title=' + mw_slug

    if article is not None:

        body_html, art_metadata, images = parser(article, redirect_target)

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
        print(f"{page_title}: article not found!")


async def make_redirect_article(article_title: str, target_redirect):
    """
    Update moved article (source, eg the previous version of the article,
    before the rename) to display a redirect page template.
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

                # remove everything from inside body.main
                # except <h1>
                for item in soup.body.main.children:
                    if isinstance(item, Tag):
                        if item.name != 'h1':
                            item.decompose()

                            
                redirect = f"<p>This page has been moved to <a href=\"{target_redirect['slug']}.html\">{target_redirect['title']}</a>.</p>"
                soup.body.main.append(redirect)
                
                output = soup.prettify(formatter=None)

            async with aiofiles.open(fn, mode='w') as f:
                await f.write(output)

            # return source article filename
            return fn.stem

        else:
            print(f"redirect-article: {article_title} not found, nothing done")
            return None


async def save_article(article: str | None, filepath: str, template: str, sem: int):

    if article is not None:
        document = template.render(article=article)
        await write_to_disk(filepath, document, sem)


async def delete_article(article_title: str):
    """
    pass article title and remove it from local wiki dir, if it exists.

    let's construct the correct filepath in here
    instead of demanding the requiring function to
    do it; in this way we uniformize what we need it
    and just assume we receive the title of the article
    and potentially its cat; if cat is None we scan the
    WIKI_DIR for a matching filename.
    """

    print(f"delete-article => {article_title}")

    p = Path(article_title)
    filename = slugify(str(p.stem))

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


async def remove_article_traces(article_title: str):
    """
    scan all HTML pages to find any bits of the given article title
    and remove any block + link pointing to it.
    """

    sem = asyncio.Semaphore(int(os.getenv('SEMAPHORE')))

    pattern = slugify(article_title)
    filepaths = search_file_content(pattern)
    print(f"remove-traces :: filepaths => {filepaths}")

    # map over each filepath and remove matched bits
    # based on the template style of each article.
    # eg, cat-index templates might be different than
    # an article template, and each match needs to remove
    # the correct DOM element in full.

    # - cat-index + index page => event-item > article.id
    # - collaborators => match <a> by href, go up one level to target parent <li>
    # - footer => what links here => ""

    tasks_html = []

    cats = config['wiki']['categories']
    cat_labels = []
    
    for k, v in cats.items():
        cat_labels.append(v['label'].lower())

    for filepath in filepaths:
        print(f"remove-traces from => {filepath}")
        filename = Path(filepath).stem

        article_html = Path(f"./{WIKI_DIR}/{filename}.html").read_text()
        soup = BeautifulSoup(article_html, 'lxml')

        # update cat-index pages if any is matching
        if filename in cat_labels:
            snippets = soup.select(f"#{pattern}")

            if len(snippets) > 0:
                for snippet in snippets:
                    snippet.decompose()

                # write updated cat-index HTML back to disk
                article_html = str(soup.prettify())
                task = write_to_disk(filename, article_html, sem)
                tasks_html.append(asyncio.ensure_future(task))

        else:
            # update links, eg footer > meta > what-links-here
            # and collaborator article page

            print(f"remove-traces :: remove links from article => {filepath}")

            links = soup.find_all("a")
            snippets = [link for link
                        in links
                        if 'href' in link.attrs and
                        link.attrs['href'].startswith(f"/{pattern}")]
            
            if len(snippets) > 0:
                for snippet in snippets:
                    parent = snippet.parent
                    if snippet.name == 'a' and parent.name == 'li':
                        parent.decompose()

                # write updated cat-index HTML back to disk
                article_html = str(soup.prettify())
                task = write_to_disk(filename, article_html, sem)
                tasks_html.append(asyncio.ensure_future(task))


    await asyncio.gather(*tasks_html)


def extract_title_from_URL(links):
    """
    we parse links from the body of the article
    and rely on the MW convention of WikiLinks, eg:
    the user type the title of a page inside {{ }}
    in this way we can extract the title of the link
    and use it to correctly fetch the page via MW's APIs
    IMPORTANT: this break in the case a link has a custom title / label.
    we try to handle this case by comparing the href of the link with
    its title, and make the title matching the href
    """

    titles = []

    for link in links:
        if 'href' in link.attrs and not link.attrs['href'].startswith('http'):
            url = None
            title = None

            url = link.attrs['href'][1:]

            if 'title' in link.attrs:
                title = link.attrs['title']
            else:
                return ''

            # url and title easily match
            if url == slugify(title):
                titles.append(title)
                
            else:
                # title is not 1:1 with url (eg custom title)
                # let's adjust title to match with url
                url_tokens = url.split('-')
                title_tokens = title.split(' ')

                new_title = []
                for idx, token in enumerate(title_tokens):
                    try:
                        if slugify(token) == url_tokens[idx]:
                            new_title.append(token)
                    except IndexError:
                        pass

                if len(new_title) > 0:
                    new_title = ' '.join(new_title)
                    titles.append(new_title)

                    
    return titles


async def update_backlinks(article, sem):
    """
    scan article for wiki links and rebuild each
    article it points to.
    this is an attempt to re-add all the backlinks
    in the articles we are re-building when we are
    either creating a new article or restoring a
    deleted one and we are removing backlinks
    from them.
    """

    soup = BeautifulSoup(article['html'], 'lxml')
    links = soup.find_all("a")
    titles = extract_title_from_URL(links)

    ENV = os.getenv('ENV')
    context = create_context(ENV)
    timeout = httpx.Timeout(10.0, connect=60.0, read=60.0)
    sem = asyncio.Semaphore(int(os.getenv('SEMAPHORE')))

    template = get_template('article')

    async with httpx.AsyncClient(verify=context, timeout=timeout) as client:
        build_tasks = []
        
        if len(titles) > 0:
            for title in titles:
                build_task = make_article(title, client)
                build_tasks.append(asyncio.ensure_future(build_task))

                articles = await asyncio.gather(*build_tasks)

                articles = [item for item
                            in articles
                            if item is not None]

            save_tasks = []
            for article in articles:
                filepath = f"{article['slug']}"

                task = save_article(article, filepath, template, sem)
                save_tasks.append(asyncio.ensure_future(task))
        
            # write all articles to disk
            await asyncio.gather(*save_tasks)
