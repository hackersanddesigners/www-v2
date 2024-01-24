from dotenv import load_dotenv
import os
from app.fetch import (
    fetch_file,
    create_context,
)
import httpx
from slugify import slugify
from bs4 import (
    BeautifulSoup,
    NavigableString,
    Tag,
)
import re
from urllib.parse import urlparse
import asyncio
import tomli
import mistletoe
from pathlib import Path
from app.file_ops import file_lookup
from app.read_settings import main as read_settings
from urllib.parse import unquote
load_dotenv()


config = read_settings()
MEDIA_DIR = os.getenv('MEDIA_DIR')


def post_process(article: str, file_URLs: [str], HTML_MEDIA_DIR: str, redirect_target: str | None = None):
    """
    update HTML before saving to disk:
    - update wikilinks to set correct title attribute
    - scan for a-href pointing to <https://hackersanddesigners.nl/...>
      and change them to be relative URLs
    - return list of images URLs
    - extract repo URL from <tool> HTML
    - do HTML clean-up for design fitting
    """

    canonical_url = config['domain']['canonical_url']
    mw_url = config['domain']['mw_url']

    soup = BeautifulSoup(article, 'lxml')

    links = soup.find_all('a')
    for link in links:
        if 'title' in link.attrs:
            link.attrs['title'] = link.text

        if link.has_attr("href"):
            if link.attrs['href'].startswith(canonical_url):
                # (eg https://hackersanddesigners.nl, no subdomain)
                # and re-write the URL to be in relative format
                # eg point to a page in *this* wiki

                url_parse = urlparse(link.attrs['href'])
                uri = slugify(url_parse.path.split('/')[-1].lower())
                matches = file_lookup(uri)

                if len(matches) > 0:
                    filename = str(matches[0]).split('.')[0]
                    new_url = "/".join(filename.split('/')[1:])
                    link.attrs['href'] = f"/{new_url}"
                else:
                    link.attrs['href'] = uri

            elif link.attrs['href'].startswith('/index.php'):

                # -- update URL for link to image
                if '=File:' in link.attrs['href']:
                    link.attrs['href'] = f"{mw_url}{link.attrs['href']}"

                    if link.img:
                        img_tag = link.img
                        img_tag.attrs['src'] = f"{mw_url}{img_tag.attrs['src']}"

                        if 'srcset' in img_tag.attrs:
                            srcset_list = [url.strip() for url in img_tag.attrs['srcset'].split(',')]

                            srcset_list_new = []
                            for item in srcset_list:
                                tokens = item.split(' ')
                                tokens[0] = f"{mw_url}{tokens[0]}"
                                srcset_new = " ".join(tokens)

                                srcset_list_new.append(srcset_new)

                            if srcset_list_new:
                                img_tag.attrs['srcset'] = ", ".join(srcset_list_new)

                        # strip images of their wrappers
                        link.parent.attrs['class'] = 'image'
                        link.replaceWith( img_tag )

                else:
                    # -- update URL of any other link

                    # this file-lookup is done to make sure
                    # articles' filename on disks matches
                    # URL used in the article files.
                    # as of <2023-11-08> i am not entirely sure
                    # this is useful, but when thinking about it
                    # it could be well helpful.

                    url_parse = urlparse(link.attrs['href'])
                    uri_title = unquote(url_parse.query.split('=')[-1])
                    uri = slugify(uri_title).lower()
                    matches = file_lookup(uri)

                    if len(matches) > 0:
                        filename = str(matches[0]).split('.')[0]
                        new_url = "/".join(filename.split('/')[1:])
                        link.attrs['href'] = f"/{new_url}"
                    else:
                        link.attrs['href'] = f"/{uri}"


    # add a tag class for iframe wrappers
    iframes = soup.find_all('iframe')
    for iframe in iframes:
        iframe.parent.attrs['class'] = 'iframe'


    # strip "thumb" images of their thumb status in their URLs
    # and get the original full size
    thumbs = soup.select('.thumb img')
    for thumb in thumbs:
        if 'src' in thumb.attrs:
            thumb.attrs['src'] = '/'.join(thumb.attrs['src'].replace('/images/thumb/', '/images/' ).split('/')[:-1])
    # strip height and width from image attribute
        for  attr in [ 'height', 'width' ]:
            if attr in thumb.attrs:
                del thumb.attrs[attr]

    # -- tool parser
    tool_repos = soup.find_all('a', class_='inGitHub')
    repos_index = []
    for repo in tool_repos:
        repos_index.append(repo.attrs['href'])

    print(f"repos-index => {repos_index}")


    # -- extract list of image URLs
    imageURLs = []
    imgs = soup.find_all('img')

    for img in imgs:
        src = img.attrs['src']
        img_name = src.split('/')[-1]
        # thumb = src.replace( '/images/', '/images/thumb/' ) + '/250px-' + img_name
        thumb = mw_url + '/thumb.php?f=' + img_name + '&w=250'
        alt = img.attrs['alt']
        imageURLs.append({ 'src': src, 'thumb': thumb, 'alt': alt })


    # -- return article HTML
    # the wiki article can be empty
    # therefore soup.contents is an empty list
    if len(soup.contents) > 0:
        t = "".join(str(item) for item in soup.body.contents)
        article = t


    return article, imageURLs, repos_index


def get_table_data_row(td):
    """
    Extracts data from HTML's <td> tag
    """

    for item in td.children:
        if isinstance(item, NavigableString):
            continue
        if isinstance(item, Tag):
            # <td> contains the data in the format
            # => {key}::{value}, let's get only the value
            content = item.string.split('::')[-1]

            return content


def get_data_from_HTML_table(article_html):
    """
    Extracts data from HTML's <tbody> tag: we map over
    each <th> element and check if it matches against any
    of the specified keys in table_keys. Those keys are taken
    from MW's own table keys and it's the subset of data we
    care about.
    """

    table_keys = ['Name', 'Location', 'Date', 'Time', 'PeopleOrganisations', 'Type']

    soup = BeautifulSoup(article_html, 'lxml')
    table = soup.find('tbody')

    # <tr> => table-row
    # <th> => table-header (where we check for a given key)
    # <td> => table-datacell (where we fetch our desired content)

    info = {}

    if table is not None:
        for tr in table.children:
            # we skip DOM strings and look only for DOM tags
            if isinstance(tr, NavigableString):
                continue
            if isinstance(tr, Tag):
                table_key = tr.th

                if table_key is not None and table_key.string is not None:
                    table_key = table_key.string.strip()

                    if  table_key in table_keys:
                        if tr.td:
                            info[table_key.lower()] = None
                            info[table_key.lower()] = get_table_data_row(tr.td)

        table.decompose()

    return info


def get_metadata(article):
    """
    extract wiki template tags from article, if any.
    extract article category
    """

    metadata = {
        "info": {},
        "categories": [],
    }

    info = get_data_from_HTML_table(article['text'])
    metadata['info'] = info

    cats = config['wiki']['categories']
    cat_keys = cats.keys()
    categories = get_category(article['categories'], cats)
    metadata['categories'] = [slugify(cat) for cat in categories]

    return metadata


def get_category(categories, cats) -> [str]:

    cat_fallback = None
    cat_fallback_key = ""
    for k, v in cats.items():
        if v['fallback']:
            cat_fallback_key = k
            cat_fallback = v

    cat_fallback_label = cat_fallback['label']

    if len(categories) > 0:
        # TODO fix this by changing the Article template in the
        # MediaWiki with another more category-bounded template
        # <2023-12-20> manually removing the 'Article' category
        # part of every wiki entry created through the Create New Article Page
        # button, as it add the category `Article` by default.

        return [cat['category'] for cat
             in categories
             if not cat['category'] == 'Article']

    else:
        return [cat_fallback_label]


async def parser(article: dict[str, int], redirect_target: str | None = None):
    """
    - get page body (HTML)
    - get article's metadata
    - get article images' URL
    """

    print(f"parsing article {article['title']}...")

    HTML_MEDIA_DIR = '/'.join(MEDIA_DIR.split('/')[1:])

    metadata = get_metadata(article)

    body_html, imageURLs, repos_index = post_process(article['text'],
                                                     article['images'],
                                                     HTML_MEDIA_DIR,
                                                     redirect_target)

    metadata['repos_index'] = repos_index
    
    print(f"parsed {article['title']}!")

    return body_html, metadata, imageURLs
