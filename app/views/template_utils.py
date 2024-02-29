from typing import Any
from urllib.parse import quote_plus

import arrow
import jinja2
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from slugify import slugify


def get_template(template: str) -> jinja2.environment.Template:
    """
    Helper function to load the correct template for Jinja.
    """

    template = template.lower()

    env = Environment(loader=FileSystemLoader("app/views/templates"), autoescape=True)
    env.filters["slug"] = make_url_slug
    env.filters["ts"] = make_timestamp

    try:
        t = env.get_template(f"{template}.html")

    except TemplateNotFound:
        print(f"template-not-found! => {template}")
        t = env.get_template("article.html")

    return t


def make_url_slug(url: str) -> str | None:
    """
    Convert given url to a slug version of itself.
    """

    if url:
        return slugify(url)

    return url


def make_mw_url_slug(url: str) -> str | None:
    """
    Convert given url to a MediaWiki friendly format.
    """

    if url:
        return quote_plus(url.replace(" ", "_"))

    return url


def make_timestamp(t: str | None) -> str | None:
    """
    Shape given timestamp string into a standard
    timestamp format.
    """

    if t:
        ts = arrow.get(t).to("local").format("YYYY-MM-DD")
        return ts

    return t


def make_timestamp_full(t: str | None) -> str | None:
    """
    Shape given timestamp string into a standard
    timestamp format, including hours, minutes and seconds.
    """

    if t:
        ts = arrow.get(t).to("local").format("YYYY-MM-DD HH:mm:ss")
        return ts

    return t


def extract_datetime(value: str | None) -> list[str] | str | None:
    """
    Extract datetime string from given value.

    Article.metadata's date and time could be
    constructed with a <start>-<end> format
    eg. date: <2023-04-12>-<2023-04-16>
        time: <18:00>-<21:00>
    """

    if value is not None:
        tokens = value.split("-")

        if len(tokens) <= 2:
            return tokens

        elif len(tokens) > 2:
            return None

    return value


def ts_pad_hour(tokens: str) -> str | None:
    """
    Helper function to add an extra 0 to the begining
    of the hour token if necessary.
    """

    hour = tokens[0]

    if len(hour) == 1:
        ts = f"0{hour}:{tokens[1]}"
        return ts

    else:
        return ":".join(tokens)


def paginator(
    items: list[dict[Any, Any]], list_size: int, cursor: int | None
) -> dict[str, list[int] | list[dict[Any, Any]] | dict[str, int | None] | int | None]:
    """
    Paginate over the given list of items by the specified list_size.
    The function returns back a dictionary with a cursor value that
    is used to navigate through the entire list.
    """

    cursors = []
    pagination = []
    cur_prev = None
    cur_next = None

    if len(items) == 0:
        return {
            "pages": pagination,
            "data": items,
            "nav": {
                "current": cursor,
                "prev": cur_prev,
                "next": cur_next,
            },
        }

    for i in range(len(items)):
        pagenum, offset = divmod(i, list_size)
        if offset == 0:
            cursors.append(i)

    # cursor eg => [0, 50, 100, 150, 200]
    # we use this value to set the left-hand side of the slice command
    # eg where we want to start slicing from

    for idx, page in enumerate(cursors):
        pagination.append(idx)

    data = items[cursors[cursor] : (cursors[cursor] + list_size)]

    if cursor is not None:
        if cursor > 0:
            cur_prev = cursor - 1

        if cursor < len(cursors) - 1:
            cur_next = cursor + 1

    return {
        "pages": pagination,
        "data": data,
        "nav": {
            "current": cursor,
            "prev": cur_prev,
            "next": cur_next,
        },
    }
