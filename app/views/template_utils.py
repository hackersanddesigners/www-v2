import arrow
from slugify import slugify


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
