from dotenv import load_dotenv
import os
import asyncio
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from slugify import slugify
from write_to_disk import main as write_to_disk
from build_article import get_article
import arrow
import json
import wikitextparser as wtp
from parser import get_metadata
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


def date_split(date: str):

    dates = date.split('-')
    if len(dates) == 2:
        return f"{dates[0]} – {dates[1]}"
    else:
        return date


def dt_to_ISO8601(value: str):
    return arrow.get(value, 'YYYY/MM/DD').format('YYYY-MM-DD')


def ISO8601_to_dt(value):
    return arrow.get(value).format('YYYY-MM-DD')


def extract_datetime(value):
    # article.metadata's date and time could be
    # constructed with a <start>-<end> format
    # eg date: <2023-04-12>-<2023-04-16>
    #    time: <18:00>-<21:00>
    # let's parse this out and check if each
    # field has multiple values, then
    # convert the first (or only) value
    # into a unix timestamp

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


async def make_event_index(articles, cat):

    filters = {
        'slug': make_url_slug,
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

        article['metadata']['dates']['start'] = arrow.get(article_ts['start']).format('YYYY-MM-DD')
        article['metadata']['times']['start'] = arrow.get(article_ts['start']).format('HH:mm')

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
            
    article = {
        'title': cat,
        'slug': slugify(cat),
        'events': events
    }

    print('events.happening =>', events['happening'])
    print('events.upcoming =>', events['upcoming'])

    sem = None
    document = template.render(article=article)
    await write_to_disk(article['slug'], document, sem)
