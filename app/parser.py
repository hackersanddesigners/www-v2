from dotenv import load_dotenv
import os
from typing import Optional
from wikitexthtml import Page
import wikitextparser as wtp
from app.fetch import (
    article_exists,
    fetch_file,
    file_exists,
    create_context,
)
import httpx
from slugify import slugify
from bs4 import BeautifulSoup
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

class WikiPage(Page):

    # remove `wiki` as first stem in tree-path from MEDIA_DIR
    # so that HTML URI works correctly
    HTML_MEDIA_DIR = '/'.join(MEDIA_DIR.split('/')[1:])

    WIKI_DIR = Path(os.getenv('WIKI_DIR'))
    download_image = config['wiki']['media']

    file_URLs = []

    def page_load(self, page) -> str:
        """
        Load the page indicated by "page" and return its body.
        """

        return page['revisions'][0]['slots']['main']['content']

    def page_exists(self, page: str) -> bool:
        """
        Return True if and only if the page exists.
        (check if article exists in the fs)
        """

        return article_exists(page)

    def template_load(self, template: str) -> str:
        """
        Load the template indicated by "template" and return its body.
        """

        # print('template-load =>', [self, template])
        # do we use templates?
        return template

    def template_exists(self, template: str) -> bool:
        """
        Return True if and only if the template exists.
        """

        # print('template-exists =>', [self, template])
        # see above
        return

    def file_exists(self, file: str) -> bool:
        """
        Return True if and only if the file (upload) exists:
        - if archive-mode is on, we check if the file exists on disk
        - else we do an HTTP ping to the MW API
        """

        # we're doing our checks directly in file_fetch
        # but we need to return True / False anyway
        # else wikitexthtml won't create an <img> tag
        # but only an <a>

        if self.download_image:
            f = Path(file)
            filepath = f"{slugify(f.stem)}{f.suffix}"
            return file_exists(filepath, self.download_image)
        else:
            filename = f"File:{file}"
            return file_exists(filename, self.download_image)


    async def file_fetch(self, file: str) -> bool:
        """
        If archive-mode: fetch the file indicated by "file" and save it to disk,
        only if a newer version of the one already saved to disk exists
        (we use timestamps between local and upstream file for this).
        Else simply do an HTTP API call to return the file URL to MW and store
        that URL to be used later in post-processing.
        """

        if not self.download_image:
            t = await fetch_file(file, self.download_image)
            self.file_URLs.append(t[1])
            return t[0]
        else:
            return await fetch_file(file, self.download_image)

    def clean_url(self, url: str) -> str:
        """
        Clean "url" (which is a wikilink) to become a valid URL to call.
        """

        # -- convert it to slugified so it correctly points to a filepath
        # -- insert category to URL: scan dir with given wiki URL
        #    and match any existing filepath in WIKI_DIR, then extract
        #    category (eg sub-dir) from it

        filename = slugify(url.lower())
        paths = file_lookup(filename)

        if len(paths) > 0:
            fn = paths[0]
            new_url = f"{fn.parent.stem}/{slugify(str(fn.stem))}"
            return new_url
        else:
            return filename

    def clean_title(self, title: str) -> str:
        """
        Clean "title" (which is a full pagename) to become more human readable.
        """

        # do we use this? set it anyway for "future-proofness" / archeology
        return title

    def file_get_link(self, url: str) -> str:
        """
        Get the link to a file (for the "a href" of the File).
        """

        f = Path(url)
        filepath = f"{slugify(f.stem)}{f.suffix}"
        return f"/{self.HTML_MEDIA_DIR}/{filepath}"

    def file_get_img(self, url: str, thumb: Optional[int] = None) -> str:
        """
        Get the "img src" to a file.
        If thumb is set, a thumb should be generated of that size.
        """

        f = Path(url)
        filepath = f"{slugify(f.stem)}{f.suffix}"
        return f"/{self.HTML_MEDIA_DIR}/{filepath}"


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


def get_tool_metadata(article_wtp: str):

    tool_keywords = re.findall(r"<tool(.*?)/>", article_wtp)

    tool_key = None
    for tk in tool_keywords:
        tool_key = tk.strip()

    if tool_key is None:
        return None

    else:

        repo = make_tool_repo(tool_key, config['tool-plugin'])

        base_URL = config['tool-plugin']['host'][repo['host']][1]
        URL = f"{base_URL}/{repo['user']}/{repo['repo']}"

        return {"uri": URL, "label": repo['host']}


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


async def pre_processpost_(article, wiki_page, article_wtp) -> str:
    """
    - update wikilinks [[<>]] to point to correct locations,
      so that WikiTextParser does its job just fine.
    - check for any malformed (and known / used) wiki tags,
      for instance the gallery tag: either try to fix it
      (if knowning how), or else report it somewhere so that
      the wiki article can be fixed instead
    - if redirect is not None, extend article.body w/ redirect link
    """

    # <2022-10-13> as we are in the process of "designing our own TOC"
    # we need to inject `__NOTOC__` to every article to avoid
    # wikitexthtml to create a TOC
    article_wtp.insert(0, '__NOTOC__')

    for template in article_wtp.templates:
        # save template value somewhere if needed
        # before running below code
        article['template'] = template.name.strip()
        del template[:]

    tasks = []
    for wikilink in article_wtp.wikilinks:

        if wikilink.title.lower().startswith('category:'):
            cat = wikilink.title.split(':')[-1]
            del wikilink[:]

        elif wikilink.title.lower().startswith('file:'):
            task = wiki_page.file_fetch(wikilink.title)
            tasks.append(asyncio.ensure_future(task))

        else:

            # -- convert normal wikilink to standard URL

            # most times only a wikilink like this is added:
            # [Title of Other Page]
            # wikilink.title => Title of Other Page
            # wikilink.text => None
            # wikilink.target => Title of Other Page
            #
            # and Mediawiki automatically converts that into a proper URL,
            # so we set wikilink.text to either wikilink.text / wikilink.target
            # then wikilink.target is slugified afterwards in the WikiPage
            # clean_url function.

            # remove `:` from target otherwise wikitexthtml sees that as a MW namespace
            # after wikitexthtml parsed the link, we run clean_url and slugify it
            # so we can point it to the correct HTML file on disk
            wikilink.target = wikilink.target.replace(':', '')


            wikilink.text = wikilink.text or wikilink.target


    await asyncio.gather(*tasks)


    for tag in article_wtp.get_tags():

        # TODO: scan through all wiki articles
        # and save in db all tags as tag.name + tag.contents
        # then check which ones are often malformed / needs care;
        #
        # make sure syntax is "strict"
        # eg image syntax starts with `File:<filepath>`
        # note: if a filepath is malformed and we know
        # it does not exists in the wiki, what to do?
        # => must be updated in the wiki; we don't try to fix
        #    wiki content on-the-fly

        if tag.name == 'gallery':
            gallery_files = tag.contents.split('\n')
            gallery_files = [f.split('|')[0] for f in gallery_files]
            gallery_files = [f.strip() for f in gallery_files if f]

            gallery_contents = []
            tasks = []
            for gallery_f in gallery_files:
                if not gallery_f.startswith('File:'):
                    f = 'File:' + gallery_f
                    gallery_contents.append(f)
                    tag.contents = '\n'.join(gallery_contents)

                    task = wiki_page.file_fetch(f)
                    tasks.append(asyncio.ensure_future(task))


            await asyncio.gather(*tasks)


    # -- return article as string
    return article_wtp.string


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


def get_metadata_field(field):

    if field is not None:
        return field.value.strip()
    else:
        return None


def get_metadata(article):
    """
    extract wiki template tags from article, if any.
    extract article category
    """

    cats = config['wiki']['categories']
    cat_keys = cats.keys()

    metadata = {
        "categories": [],
    }

    # templates = article.templates
    templates = []

    if len(templates) > 0:

        templates_keys = ['Name', 'Location', 'Date', 'Time', 'PeopleOrganisations', 'Type']

        for t in article.templates:
            label = t.name.strip()
            if label in cat_keys:
                if not cats[label]['fallback']:
                    cat_label = cats[label]['label']
                    metadata['category'] = slugify(cat_label)

            # collect all metadata from article.template table
            for key in templates_keys:
                metadata[key.lower()] = get_metadata_field(t.get_arg(key))


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
    - instantiate WikiPage class
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
