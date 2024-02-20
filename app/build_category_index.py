import os
from pathlib import Path
import asyncio
from app.fetch import (
    create_context,
    query_continue,
)
import httpx
from app.views.views import (
    make_article_event,
    make_event_index,
    make_collaborators_index,
    make_publishing_index,
    make_tool_index,
    make_article_index,
)
from app.views.template_utils import (
    get_template,
    paginator,
)
from app.read_settings import main as read_settings
from app.build_article import (
    make_article,
    save_article,
)
from app.file_ops import write_to_disk
from bs4 import (
    BeautifulSoup,
)
from app.log_to_file import main as log


ENV = os.getenv('ENV')
URL = os.getenv('BASE_URL')
WIKI_DIR = os.getenv('WIKI_DIR')
config = read_settings()


async def make_category_index(cat: str):
    """
    Build Index page of the specified category.
    """

    cat_key = None
    cat_label = None

    cats = config['wiki']['categories']

    for k, v in cats.items():
        if k.lower() == cat:
            cat_key = k
            cat_label = cats[k]['label']


    if not cat_key:
        print(f"make-category-index: the 'cat: {cat}' has not matched with any\n",
              f"of the following categories:\n",
              f"{list(cats.keys())}")
        return None

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
    timeout = httpx.Timeout(10.0, connect=60.0, read=60.0)
    async with httpx.AsyncClient(verify=context, timeout=timeout) as client:

        # -- get full list of entries from category
        data = []
        translation_langs = [config['wiki']['default'],
                             config['wiki']['translation_langs'][0]]
        
        async for response in query_continue(client, URL, params):
            response = response['categorymembers']
            title = response[0]['title']

            if len(response) > 0 and 'missing' in response[0]:
                print(f"the page could not be found => {title}")

            else:
                data.extend(response)
                    

        # TODO the code above can be replaced with get_category from build_wiki.py
        # --

        translation_langs = [config['wiki']['default'],
                             config['wiki']['translation_langs'][0]]

        art_tasks = []
        for article in data:
            # filter out translated article
            title = article['title']
            lang_stem = title.split('/')[-1]
            tokens = title.split('/')
            
            if lang_stem not in translation_langs:
                task = make_article(article['title'], client)
                art_tasks.append(asyncio.ensure_future(task))

        prepared_articles = await asyncio.gather(*art_tasks)
        await log('info',
                  f"prep-articles {cat_key} => un-filtered {len(prepared_articles)}\n",
                  sem=None)
        
        prepared_articles = [item for item
                             in prepared_articles 
                             if item is not None]
        await log('info',
                  f"prep-articles {cat_key} => filtered {len(prepared_articles)}\n",
                  sem=None)

        article = None
        sorting = None

        if cat_label == 'Events':
            article = await make_event_index(prepared_articles, cat_key, cat_label)

        elif cat_label == 'Collaborators':
            article = await make_collaborators_index(prepared_articles, cat_key, cat_label)

        elif cat_label == 'Publishing':
            article = await make_publishing_index(prepared_articles, cat_key, cat_label)

        elif cat_label == 'Tools':
            article = await make_tool_index(prepared_articles, cat_key, cat_label)

        elif cat_label == 'Articles':
            article = await make_article_index(prepared_articles, cat_key, cat_label)


        if article:
            return (article)

        
async def build_categories(categories: list[str], template, sem):
    """
    Build all category index pages.
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
        task = write_to_disk(filepath, cat_index['html'], sem)
        cat_tasks_html.append(asyncio.ensure_future(task))
        
    await asyncio.gather(*cat_tasks_html)


async def update_categories(article, sem):
    """
    Update Index page for each value part of `categories`.
    We don't rebuild the whole Index page from scratch by parsing every
    article in it. Rather, we just update the article's info
    in the Index page that has triggered the update_categories function.
    """

    # - select index-template by `cat`
    # - build updated article item HTML snippet for category index
    # - use bs4 to search and replace previous article-item with new one
    # - check if article item list needs to be re-sorted?

    cat_tasks_html = []

    cats = config['wiki']['categories']
    cat_label = None
    
    for cat in article['metadata']['categories']:
        
        # -- get cat_label and check if it matches
        #    with defined settings.categories
        for k, v in cats.items():
            if k.lower() == cat:
                cat_label = cats[k]['label']

        if cat_label is None:
            print(f"update-categories err => no cat_label set for {cat}")
            return


        # if article is an event we need to do more work
        # on the data structure before we pass it to the template.
        # do it here.
        prepared_article = article
        if cat == 'event':
            prepared_article = make_article_event(article)

        # make new snippet for updated article 
        template = get_template(f'partials/{cat}-item')
        snippet_new = template.render(article=prepared_article)

        # make bs4 object out of the HTML string
        snippet_new = BeautifulSoup(snippet_new, 'lxml')

        index_doc = cat_label.lower()

        # get existing cat-index HTML
        if not Path(f"./{WIKI_DIR}/{index_doc}.html").exists():
            # cat-event HTML file does not exist. let's build it from scratch
            # and write it to disk w/o doing the HTML-swap step
            # (as unnecessary at this point).
            cat_index = await make_category_index(cat)
            filepath = f"{cat_index['slug']}"
            await write_to_disk(filepath, cat_index['html'], sem=None)
            
            break

        
        index_old = Path(f"./{WIKI_DIR}/{index_doc}.html").read_text()
        
        # find cat index's list item (article snippet) matching
        # against given article's slug
        soup = BeautifulSoup(index_old, 'lxml')
        snippets_old = soup.select(f"#{article['slug']}")

        # replace matched article snippet with newer one
        article_snippet = soup.select(f"#{article['slug']}")
        if len(article_snippet) > 0:
            for item in article_snippet:
                item.replace_with(snippet_new)

            # write updated cat-index HTML back to disk
            cat_html = str(soup.prettify())
            task = write_to_disk(index_doc, cat_html, sem)
            cat_tasks_html.append(asyncio.ensure_future(task))

        else:
            # if no matching from the old snippet,
            # it means we need to insert the article snippet
            # into the page.
            # do we try to insert the snippet in the correct position
            # in the cat index list? no, we just rebuild the entire
            # page. easier and more effective than otherwise having to
            # compare against all the other article snippets and find
            # in which position the newly created or restored
            # article snippet should be inserted.

            cat_index = await make_category_index(cat)
            filepath = f"{cat_index['slug']}"
            await write_to_disk(filepath, cat_index['html'], sem=None)

            break

    await asyncio.gather(*cat_tasks_html)


    
