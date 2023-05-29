from dotenv import load_dotenv
import os
import asyncio
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from slugify import slugify
from .write_to_disk import main as write_to_disk
from .build_article import get_article, make_nav, make_article
import arrow
import json
import wikitextparser as wtp
from .parser import get_metadata, parser
from .fetch import create_context
import httpx
load_dotenv()


def get_template(template: str, filters):
    template = slugify(template)
    env = Environment(loader=FileSystemLoader('app/templates'), autoescape=True)

    if filters is not None:
        for k,v in filters.items():
            env.filters[k] = v

    try:
        t = env.get_template(f"{template}.html")

    except TemplateNotFound:
        t = env.get_template("article.html")

    return t
    

def make_url_slug(url: str):

    if url:
        return slugify(url)

    return url


def make_timestamp(t: str):

    if t:
        ts = arrow.get(t).to('local').format('YYYY-MM-DD')
        return ts


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


async def make_front_index(article_title: str):

    filters = {
        'slug': make_url_slug,
        'ts': make_timestamp,
    }

    template = get_template("index", filters)

    # - get Hackers_%26_Designers wiki page for latest news
    ENV = os.getenv('ENV')
    context = create_context(ENV)
    sem = None

    async with httpx.AsyncClient(verify=context) as client:
        metadata_only = False
        article, metadata = await make_article(article_title, client, metadata_only)

        article['slug'] = 'index'
        article['last_modified'] = metadata['last_modified']
        article['backlinks'] = metadata['backlinks']

        document = template.render(article=article)
        await write_to_disk(article['slug'], document, sem)


async def make_event_index(articles, cat, cat_label):

    filters = {
        'slug': make_url_slug,
        'ts': make_timestamp,
    }

    template = get_template(f"{cat}-index", filters)

    # events
    # - upcoming
    # - happening right now
    # - past
    #
    # order articles by date desc

    events = {
        'upcoming': [],
        'happening': [],
        'past': [],
    }

    date_now = arrow.now()

    for article in articles:

        date = extract_datetime(article['metadata']['date'])
        time = extract_datetime(article['metadata']['time'])

        article_ts = {'start': None, 'end': None}

        if date is not None and time is not None:

            tokens_start = time[0].split(':')
            ts_start = ts_pad_hour(tokens_start)

            if len(time) > 1:
                tokens_end = time[1].split(':')
                ts_end = ts_pad_hour(tokens_end)

                article['metadata']['time'] = f"{ts_start}-{ts_end}"

            else:
                article['metadata']['time'] = f"{ts_start}"

            date_start = date[0]

            # -- construct datetime start
            dts_start = f"{date_start} {ts_start}"
            article_ts['start'] = arrow.get(dts_start, 'YYYY/MM/DD HH:mm')

            if len(date) > 1:
                date_end = date[1]

                # -- construct datetime end
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
                events['happening'].append(article)

        if article_ts['start']:

            if date_now < article_ts['start']:
                events['upcoming'].append(article)

            else:
                events['past'].append(article)


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

        # --

    # -- sort events by date desc
    events['upcoming'] = sorted(events['upcoming'], key=lambda d: d['metadata']['dates']['start'], reverse=True)
    events['past'] = sorted(events['past'], key=lambda d: d['metadata']['dates']['start'], reverse=True)
    events['happening'] = sorted(events['happening'], key=lambda d: d['metadata']['dates']['start'], reverse=True)
            
    nav = make_nav()

    article = {
        'title': cat,
        'slug': slugify(cat_label),
        'events': events,
        'nav': nav
    }

    print('events.happening =>', events['happening'])
    print('events.upcoming =>', events['upcoming'])

    sem = None
    document = template.render(article=article)
    await write_to_disk(article['slug'], document, sem)


async def make_collaborators_index(articles, cat, cat_label):

    filters = {
        'slug': make_url_slug,
        'ts': make_timestamp,
    }

    template = get_template(f"{cat}-index", filters)

    # collaborators
    # list of names w/ connected projects / articles?
    # similar to MediaWiki syntax
    # {{Special:WhatLinksHere/<page title>}}

    nav = make_nav()

    article = {
        'title': cat,
        'slug': slugify(cat_label),
        'collaborators': articles,
        'nav': nav
    }

    return article

    sem = None
    document = template.render(article=article)
    await write_to_disk(article['slug'], document, sem)


async def make_publishing_index(articles, cat, cat_label):

    filters = {
        'slug': make_url_slug,
        'ts': make_timestamp,
    }

    template = get_template(f"{cat}-index", filters)

    nav = make_nav()

    article = {
        'title': cat,
        'slug': slugify(cat_label),
        'articles': articles,
        'nav': nav
    }

    return article

    sem = None
    document = template.render(article=article)
    await write_to_disk(article['slug'], document, sem)


async def make_tool_index(articles, cat, cat_label):

    filters = {
        'slug': make_url_slug,
        'ts': make_timestamp,
    }

    template = get_template(f"{cat}-index", filters)
    nav = make_nav()

    article = {
        'title': cat_label,
        'slug': slugify(cat_label),
        'articles': articles,
        'nav': nav
    }

    return article

    sem = None
    document = template.render(article=article)
    await write_to_disk(article['slug'], document, sem)


async def make_sitemap(articles):

    filters = {
        'slug': make_url_slug,
        'ts': make_timestamp,
    }

    template = get_template(f"sitemap", filters)
    nav = make_nav()

    article = {
        'title': "Sitemap",
        'slug': "sitemap",
        'articles': articles,
        'nav': nav
    }

    return article

    sem = None
    document = template.render(article=article)
    await write_to_disk(article['slug'], document, sem)



async def make_index_sections(articles_metadata, cat: str, cat_label: str):

    if cat == 'Event':
        await make_event_index(articles_metadata, cat, cat_label)

    if cat == 'Collaborators':
        await make_collaborators_index(articles_metadata, cat, cat_label)

    if cat == 'Publishing':
        await make_publishing_index(articles_metadata, cat, cat_label)

    if cat == 'Tools':
        await make_tool_index(articles_metadata, cat, cat_label)
