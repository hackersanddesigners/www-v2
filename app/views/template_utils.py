import arrow
from slugify import slugify
from urllib.parse import parse_qs, urlencode
from html import unescape


def query_check(url: str, query_key: str | None = None, query_value: str | None = None) -> str:
    """
    Check if given URL has any query parameter:
    if yes, append query value with `&` (=> ?some=query&query`)
    else update existing query key with new query value.
    """

    if query_key == 'sort_by':
        if url.query != '':

            query_params = parse_qs(url.query)
            try:
                sort_dir = query_params['sort_dir'][0]
            except KeyError:
                query_params['sort_dir'] = ['asc']
                sort_dir = 'asc'

            # if new query matches existing query key
            # update only query value;
            # else append new query to existing query param

            if query_key in query_params:

                # if clicked URL is same as current one
                # flip around sort_dir value
                if query_params['sort_by'][0] == query_value:
                
                    if sort_dir == 'asc':
                        query_params['sort_dir'][0] = 'desc'
                    else:
                        query_params['sort_dir'][0] ='asc'

                       
                query_params[query_key][0] = query_value
            
                return f"{url.path}?{urlencode(query_params, doseq=True)}"

            else:            
                url = f"{url.path}?{url.query}&{query_key}={query_value}&sort_dir={sort_dir}"
     
        else:
            return f"{url.path}?{query_key}={query_value}"

    if query_key == 'sort_dir':
        
        if url.query != '':

            query_params = parse_qs(url.query)
            try:
                sort_dir = query_params['sort_dir'][0]
            except KeyError:
                query_params['sort_dir'] = ['asc']
                sort_dir = 'asc'

            if query_key in query_params:
                
                if query_params['sort_by'][0] == query_value:

                    if sort_dir == 'asc':
                        return unescape("&#x25B2;")
                    else:
                        return unescape("&#x25BC;")

                else:
                    return f""
                

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


def paginator(items, list_size: int, cursor: int):
    
    cursors = []
    for i in range(len(items)):
        pagenum, offset = divmod(i, list_size)
        if offset == 0:
            cursors.append(i)

    # cursor eg => [0, 50, 100, 150, 200]
    # we use this value to set the left-hand side of the slice command
    # eg where we want to start slicing from

    pagination = []
    for idx, page in enumerate(cursors):
        pagination.append(idx)
        
    data = items[cursors[cursor] : (cursors[cursor] + list_size)]

    cur_prev = None
    if cursor > 0:
        cur_prev = cursor - 1
    
    cur_next = None
    if cursor < len(cursors) - 1:
        cur_next = cursor + 1

    return {
        "pages": pagination,
        "data": data,
        "nav": {
            "current": cursor,
            "prev": cur_prev,
            "next": cur_next,
        }
    }
