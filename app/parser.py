from dotenv import load_dotenv
import os
from app.fetch import (
    article_exists,
    fetch_file,
    file_exists,
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


def make_tool_repo(tool_key: str, config_tool):
    """
    Parse MW custom <tool> tag into a dictionary. We use this
    to retrieve the content of the README file from the git repo.
    """

    repo = {"host": None, "branch": [], "file": None}
    fallback_branch = config['tool-plugin']['branch_default']
    repo['branch'] = fallback_branch

    tokens = tool_key.split()

    for t in tokens:
        # let's split only `<word>=<word>` items
        if '=' in t:
            prop = t.split('=')

            if t == 'branch':
                v = prop[1][1:-1].strip()

                if v not in repo['branch']:
                    repo['branch'].append(v)

            else:
                repo[prop[0].strip()] = prop[1][1:-1].strip()

    if repo['host'] == None:
        repo['host'] = config_tool['host_default']

    if len(repo['branch']) == 0:
        repo['branch'] = config_tool['branch_default']

    if repo['file'] == None:
        repo['file'] = config_tool['file_default']


    return repo


def parse_tool_tag(tool_key):

    if tool_key is not None:

        repo = make_tool_repo(tool_key, config['tool-plugin'])

        # construct a URL for github raw link
        # so we fetch the actual README file content
        # and do whatever we like with it
        # https://raw.githubusercontent.com/<user>/<repo>/<branch>/<file>
        # suggestion: add two more fields to the <tool> syntax:
        # - host
        # - branch

        ENV = os.getenv('ENV')
        context = create_context(ENV)
        with httpx.Client(verify=context) as client:

            base_URL = config['tool-plugin']['host'][repo['host']][0]
            URL_tokens = [base_URL, repo['user'], repo['repo'], repo['branch'][0], repo['file']]

            for branch in repo['branch']:

                URL_tokens[3] = branch
                URL = "/".join(URL_tokens)

                response = client.get(URL)

                if response.status_code == 200:
                    text = response.text
                    return mistletoe.markdown(text), repo

            return False, False

    else:
        return False, False


def tool_convert_rel_uri_to_abs(items, attr, repo):
    """
    tool plugin: replace each items relative URLs to an absolute one,
    using the specified attribute
    """

    if len(items) > 0:
        for item in items:
            uri = item[attr]

            if not uri.startswith('http'):
                f = uri.split('/').pop()

                # -- handle URL to text files and binary files
                #    eg a.href and img.src
                #    <host>/<user>/<repo>/<blob?>/<branch>/<file>
                blob = ''
                base_URL = config['tool-plugin']['host'][repo['host']][0]

                if attr != 'src':
                    base_URL = config['tool-plugin']['host'][repo['host']][1]
                    blob = 'blob/'

                item[attr] = f"{base_URL}/{repo['user']}/{repo['repo']}/{blob}{repo['branch'][0]}/{f}"


def replace_img_src_url_to_mw(soup, file: str, url: str, HTML_MEDIA_DIR: str):
    """
    if archive-mode is off, replace all img src attribute,
    plus img alt and the parent a's href to point to the
    MW URL file instance
    """

    f = Path(unquote(file))

    url_match = f"/{HTML_MEDIA_DIR}/{slugify(f.stem)}{f.suffix}"
    img_tag = soup.find(src=re.compile(url_match))

    if img_tag:
        img_tag['src'] = url

        if 'alt' in img_tag.attrs:
            if img_tag['alt'] == url_match:
                img_tag['alt'] = url

                img_tag.parent['href'] = url


def post_process(article: str, file_URLs: [str], HTML_MEDIA_DIR: str, redirect_target: str | None = None):
    """
    update HTML before saving to disk:
    - add redirect text + link, if necessary
    - update wikilinks to set correct title attribute
    - replace Tool's wiki syntax to actual HTML
    - if non archive-mode: update img's src to point to MW image server
    - scan for a-href pointing to <https://hackersanddesigners.nl/...>
      and change them to be relative URLs
    """

    canonical_url = config['domain']['canonical_url']
    mw_url = config['domain']['mw_url']

    soup = BeautifulSoup(article, 'lxml')

    # TODO we don't need this, since MW should give us back a redirected page in case?
    # we insert some custom HTML to add a reference
    # that the current article has been moved to another URL
    # if redirect_target is not None:
    #     redirect = f"<p>This page has been moved to <a href=\"{slugify(redirect_target)}.html\">{redirect_target}</a>.</p>"

    #     soup.body.insert(0, redirect)

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
    # naive regex to grab the <tool ... /> string
    tool_keywords = soup.find_all(string=re.compile(r"<tool(.*?)/>"))

    for tk in tool_keywords:
        tool_key = tk.strip()
        tool_HTML, repo = parse_tool_tag(tool_key)

        if tool_HTML is not False and repo is not False:
            tool_soup = BeautifulSoup(tool_HTML, 'lxml')

            # change all relative URIs to absolute
            links = tool_soup.find_all('a')
            tool_convert_rel_uri_to_abs(links, 'href', repo)

            imgs = tool_soup.find_all('img')
            tool_convert_rel_uri_to_abs(imgs, 'src', repo)

            # append updated tool_soup to the article's <body>
            tk.parent.parent.extend(tool_soup.body.contents)
            # remove <p> with inside the string `<tool .../>`
            tk.parent.decompose()


    # -- return article HTML
    # the wiki article can be empty
    # therefore soup.contents is an empty list
    if len(soup.contents) > 0:
        t = "".join(str(item) for item in soup.body.contents)
        return t

    else:
        return article


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


async def get_images(HTML_MEDIA_DIR: str, images_list: list[str]):
    """
    Prepare list of images for given Index page.
    If not copying images locally, we need to fetch them
    from the wiki one by one and it slows down the loading
    of the page. TODO => move to create static index pages?
    """

    download_image = config['wiki']['media']

    images = []
    tasks = []

    async def file_fetch(file: str, download: bool) -> bool:
        if not download:
            t = await fetch_file(file, download_image)
            images.append(t[1])
        else:
            t = await fetch_file(file, download)
            images.append(t[1])

    for image in images_list:
        image = f"File:{image}"
        task = file_fetch(image, download_image)
        tasks.append(asyncio.ensure_future(task))

    await asyncio.gather(*tasks)
    return images


def get_category(categories, cats) -> [str]:

    cat_fallback = None
    cat_fallback_key = ""
    for k, v in cats.items():
        if v['fallback']:
            cat_fallback_key = k
            cat_fallback = v

    cat_fallback_label = cat_fallback['label']

    if len(categories) > 0:
        return [cat['category'] for cat in categories]

    else:
        return [cat_fallback_label]


async def parser(article: dict[str, int],
                 metadata_only: bool,
                 redirect_target: str | None = None):
    """
    - if redirect is not None, make custom HTML page
    - else, get page body (HTML)
    - return either version
    - return dict with article metadata to build index pages
    """

    print(f"parsing article {article['title']}...")

    HTML_MEDIA_DIR = '/'.join(MEDIA_DIR.split('/')[1:])

    metadata = get_metadata(article)
    images = await get_images(HTML_MEDIA_DIR, article['images'])

    if metadata_only:
        return metadata, images


    body_html = post_process(article['text'],
                             article['images'],
                             HTML_MEDIA_DIR,
                             redirect_target)

    print(f"parsed {article['title']}!")

    return body_html, metadata, images
