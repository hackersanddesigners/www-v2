from dotenv import load_dotenv
import os
import asyncio
import aiofiles
from aiofiles import os as aos
from bs4 import BeautifulSoup
from .template_utils import (
    get_template,
    make_url_slug,
    make_timestamp,
)
from slugify import slugify
from app.file_ops import (
    write_to_disk,
    file_lookup,
)
from app.build_article import (
    make_nav,
    make_footer_nav,
    make_article,
)
import arrow
import json
from app.parser import (
    get_metadata,
    parser,
)
from app.fetch import (
    create_context,
    fetch_category,
)
import httpx
from app.log_to_file import main as log
load_dotenv()


def date_split(date: str):

    dates = date.split('-')
    if len(dates) == 2:
        return f"{dates[0]} – {dates[1]}"
    else:
        return date


def extract_datetime(value):
    # article.metadata's date and time could be
    # constructed with a <start>-<end> format
    # eg date: <2023-04-12>-<2023-04-16>
    #    time: <18:00>-<21:00>

    if value is not None:
        tokens = value.split('-')

        if len(tokens) <= 2:
            return tokens

        elif len(tokens) > 2:
            return None


def ts_pad_hour(tokens):
    hour = tokens[0]

    if len(hour) == 1:
        ts = f"0{hour}:{tokens[1]}"
        return ts

    else:
        return ":".join(tokens)


def normalize_data(item):
    """
    Convert None to "" (empty string) if value
    is missing, else make value uppercase.
    """

    if item:
        return item.upper()
    else:
        return ''

# -- front-page

async def make_front_index(home_art: str, home_cat: str):
    
    ENV = os.getenv('ENV')
    context = create_context(ENV)
    timeout = httpx.Timeout(10.0, connect=60.0)
    async with httpx.AsyncClient(verify=context) as client:

        # list of articles w/ `highlight` cat
        data = await fetch_category(home_cat, client)
        art_tasks = []
        for article in data:
            task = make_article(article['title'], client)
            art_tasks.append(asyncio.ensure_future(task))

        highlight_articles = await asyncio.gather(*art_tasks)
        highlight_articles = [item for item
                             in highlight_articles
                             if item is not None]

        # `Hackers & Designers` article
        article = await make_article(home_art, client)
        article['slug'] = 'index'
        article['last_modified'] = article['metadata']['last_modified']
        article['backlinks'] = article['metadata']['backlinks']

        # add highlights to dict
        article['highlights'] = highlight_articles

        # -- upcoming events
        upcoming_events = []
        events_path = file_lookup("events")

        current_timestamp = arrow.now().to('local')

        if (events_path[0]):
            if await aos.path.exists(events_path[0]):
                async with aiofiles.open(events_path[0], mode='r') as f:
                    tree = await f.read()
                    soup = BeautifulSoup(tree, 'lxml')

                    upcoming_events = soup.find_all("article", {"class": "when-upcoming" })
                    upcoming_events_str = []
                    
                    for event in upcoming_events:
                        # check if upcoming-event's date is bigger than
                        # current timestamp. this helps to keep the list of
                        # upcoming events even when no change is done to an event
                        # and by consequence to the events page, which we
                        # use above to query for all the upcoming events.
                        
                        event_date = arrow.get(event.attrs['data-start'])
                        if event_date > current_timestamp:
                            upcoming_events_str.append(str(event))

                            
        article['upcoming'] = upcoming_events_str

        return article


# -- events

def make_article_event(article):
    """
    Extend data for single Event article.
    """
    
    date = None
    time = None

    date_now = arrow.now()

    if 'date' in article['metadata']['parsed_metadata']:
        date = extract_datetime(article['metadata']['parsed_metadata']['date'])

    if 'time' in article['metadata']:
        time = extract_datetime(article['metadata']['parsed_metadata']['time'])

    article_ts = {'start': None, 'end': None}

    if date is not None and time is not None:

        tokens_start = time[0].split(':')
        ts_start = ts_pad_hour(tokens_start)

        if len(time) > 1:
            tokens_end = time[1].split(':')
            ts_end = ts_pad_hour(tokens_end)

            article['metadata']['parsed_metadata']['time'] = f"{ts_start}-{ts_end}"

        else:
            article['metadata']['parsed_metadata']['time'] = f"{ts_start}"

        # -- construct datetime start
        date_start = date[0]

        dts_start = f"{date_start} {ts_start}"
        article_ts['start'] = arrow.get(dts_start, 'YYYY/MM/DD HH:mm')

        if len(date) > 1:
            # -- construct datetime end
            date_end = date[1]

            dts_end = f"{date_end} {ts_end}"
            article_ts['end'] = arrow.get(dts_end, 'YYYY/MM/DD HH:mm')

    elif date is not None:
        date_start = date[0]

        dts_start = f"{date_start}"
        article_ts['start'] = arrow.get(dts_start, 'YYYY/MM/DD')

        if len(date) > 1:
            date_end = date[1]

            dts_end = f"{date_end}"
            article_ts['end'] = arrow.get(dts_end, 'YYYY/MM/DD')

    if article_ts['start'] is not None and article_ts['end'] is not None:

        if date_now > article_ts['start'] and date_now < article_ts['end']:
            article['metadata']['when'] = 'happening'
            # events['happening'].append(article)

    if article_ts['start']:

        if date_now < article_ts['start']:
            article['metadata']['when'] = 'upcoming'
            # events['upcoming'].append(article)

        else:
            article['metadata']['when'] = 'past'
            # events['past'].append(article)

    # -- prepare article dates for template

    article['metadata']['dates'] = {'start': None, 'end': None}
    article['metadata']['times'] = {'start': None, 'end': None}

    if article_ts['start'] is not None:
        article['metadata']['dates']['start'] = arrow.get(article_ts['start']).format('YYYY-MM-DD')
        article['metadata']['times']['start'] = arrow.get(article_ts['start']).format('HH:mm')
    else:
        article['metadata']['dates']['start'] = None
        article['metadata']['times']['start'] = None

    if article_ts['end'] is not None:
        article['metadata']['dates']['end'] = arrow.get(article_ts['end']).format('YYYY-MM-DD')
        article['metadata']['times']['end'] = arrow.get(article_ts['end']).format('HH:mm')
    else:
        article['metadata']['dates']['end'] = None
        article['metadata']['times']['end'] = None
    

    return article
        

async def make_event_index(articles: list[dict[str]], cat: str, cat_label: str):

    template = get_template(f"{cat}-index")

    # events
    # - upcoming
    # - happening right now
    # - past
    #
    # order articles by date desc

    # events = {
    #     'upcoming': [],
    #     'happening': [],
    #     'past': [],
    # }

    events = []
    types = []

    date_now = arrow.now()


    for article in articles:
        if article:

            prepared_article = make_article_event(article)

            if (
                    prepared_article['metadata'] and
                    prepared_article['metadata']['parsed_metadata'] and
                    prepared_article['metadata']['parsed_metadata']['type']
            ):
                
                event_type = prepared_article['metadata']['parsed_metadata']['type']
                if event_type and event_type not in types:
                    types.append(event_type)

            events.append(article)


    # -- sorting events by date desc

    # events['upcoming'] = sorted(events['upcoming'], key=lambda d: d['metadata']['dates']['start'], reverse=True)
    # events['past'] = sorted(events['past'], key=lambda d: d['metadata']['dates']['start'], reverse=True)
    # events['happening'] = sorted(events['happening'], key=lambda d: d['metadata']['dates']['start'], reverse=True)

    events = sorted( events, key=lambda d: d['metadata']['dates']['start'] or "" , reverse=True)
    await log('info',
              f"make-event => un-filtered {len(events)}\n",
              sem=None)
            
    await log('info',
              f"make-event => filtered {len(events)}\n",
              sem=None)
    
    types = sorted( types, key=str.lower )

    nav = make_nav()
    footer_nav = make_footer_nav()

    article = {
        'title': cat,
        'slug': slugify(cat_label),
        'events': events,
        'types': types,
        'nav': nav,
        'footer_nav': footer_nav,
        'html': '',
    }

    document = template.render(article=article)
    article['html'] = document

    return article


# -- collaborators

async def make_collaborators_index(articles, cat: str, cat_label: str):

    template = get_template(f"{cat}-index")

    # collaborators
    # list of names w/ connected projects / articles?
    # similar to MediaWiki syntax
    # {{Special:WhatLinksHere/<page title>}}

    nav = make_nav()
    footer_nav = make_footer_nav()

    articles = sorted(articles,
           key=lambda d: d['metadata']['creation'],
           reverse=True)

    article = {
        'title': cat,
        'slug': slugify(cat_label),
        'collaborators': articles,
        'nav': nav,
        'footer_nav': footer_nav,
        'html': '',
    }

    document = template.render(article=article)
    article['html'] = document

    return article

# -- publishing

async def make_publishing_index(articles, cat: str, cat_label: str):

    template = get_template(f"{cat}-index")
    nav = make_nav()
    footer_nav = make_footer_nav()

    articles = sorted(articles,
           key=lambda d: d['metadata']['creation'],
           reverse=True)

    article = {
        'title': cat,
        'slug': slugify(cat_label),
        'articles': articles,
        'footer_nav': footer_nav,
        'nav': nav,
        'html': '',
    }

    document = template.render(article=article)
    article['html'] = document

    return article

# -- tool

async def make_tool_index(articles, cat: str, cat_label: str):

    template = get_template(f"{cat}-index")
    nav = make_nav()
    footer_nav = make_footer_nav()

    articles = sorted(articles,
                      key=lambda d: d['metadata']['creation'],
                      reverse=True)

    article = {
        'title': cat_label,
        'slug': slugify(cat_label),
        'articles': articles,
        'nav': nav,
        'footer_nav': footer_nav,
        'html': '',
    }

    # print( json.dumps( article, indent=2 ) )

    document = template.render(article=article)
    article['html'] = document

    return article

# -- search

async def make_search_index(articles, query):

    template = get_template(f"search-index")
    nav = make_nav()
    footer_nav = make_footer_nav()

    for result in articles:
        print(json.dumps(result, indent=2))
        result['slug'] = slugify(result['title'])

    article = {
        'title': "\"" + query + "\" search results",
        'slug': "search",
        'query': query,
        'results': articles,
        'footer_nav': footer_nav,
        'nav': nav
    }

    return article

# -- article

async def make_article_index(articles, cat, cat_label):

    template = get_template(f"{cat}-index")

    nav = make_nav()
    footer_nav = make_footer_nav()

    article = {
        'title': cat,
        'slug': slugify(cat_label),
        'articles': articles,
        'nav': nav,
        'footer_nav': footer_nav,
        'html': '',
    }

    document = template.render(article=article)
    article['html'] = document

    return article
