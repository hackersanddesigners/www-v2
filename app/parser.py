from dotenv import load_dotenv
import os
from typing import Optional
from wikitexthtml import Page
import wikitextparser as wtp
from fetch import article_exists, fetch_file, file_exists, create_context
import httpx
from slugify import slugify
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse
import asyncio
import tomli
import mistletoe
from pathlib import Path
load_dotenv()


class WikiPage(Page):

    MEDIA_DIR = os.getenv('MEDIA_DIR')

    # remove `wiki` as first stem in tree-path from MEDIA_DIR
    # so that HTML URI works correctly
    HTML_MEDIA_DIR = '/'.join(MEDIA_DIR.split('/')[1:])

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
        - we check if the file exists on disk
        """

        # we're doing our checks directly in file_fetch
        # but we need to return True / False anyway
        # else wikitexthtml won't create an <img> tag
        # but only an <a>

        f = Path(file)
        filepath = f"{slugify(f.stem)}{f.suffix}"
        return file_exists(filepath)

    async def file_fetch(self, file: str) -> bool:
        """
        Fetch the file indicated by "file" and save it to disk,
        only if a newer version of the one already saved to disk exists
        (we use timestamps between local and upstream file for this)
        """

        return await fetch_file(file)

    def clean_url(self, url: str) -> str:
        """
        Clean "url" (which is a wikilink) to become a valid URL to call.
        """

        # convert it to slugified version and then append `.html`
        # so it correctly points to a filepath

        new_url = slugify(url)
        return f"{new_url}.html"

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
    tokens = tool_key.split()

    repo = {"host": None, "branch": None}
    for t in tokens:
        # let's split only `<word>=<word>` items
        if '=' in t:
            prop = t.split('=')
            repo[prop[0].strip()] = prop[1][1:-1].strip()

    if repo['host'] == None:
        repo['host'] = config_tool['host_default']

    if repo['branch'] == None:
        repo['branch'] = config_tool['branch_default']

    return repo


def get_tool_metadata(article_wtp: str):

    tool_keywords = re.findall(r"<tool(.*?)/>", article_wtp)

    tool_key = None
    for tk in tool_keywords:
        tool_key = tk.strip()

    if tool_key is None:
        return None

    else:

        with open("settings.toml", mode="rb") as f:
            config = tomli.load(f)

        repo = make_tool_repo(tool_key, config['tool-plugin'])

        base_URL = config['tool-plugin']['host'][repo['host']][1]
        URL = f"{base_URL}/{repo['user']}/{repo['repo']}"

        return {"uri": URL, "label": repo['host']}


def parse_tool_tag(tool_key):

    if tool_key is not None:

        with open("settings.toml", mode="rb") as f:
            config = tomli.load(f)

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
            URL = f"{base_URL}/{repo['user']}/{repo['repo']}/{ repo['branch'][0] }/{repo['file']}"

            response = client.get(URL)

            # we're assuming that in case the URL return 404
            # it's the branch name the problem, so we fallback
            # to two options: main, master. we try both,
            # in case we get still 404, return nothing
            if response.status_code == 200:
                text = response.text
                return mistletoe.markdown(text), repo

            elif response.status_code == 404:

                # let's remove the previous branch value from the list
                # since it brought us to a 404
                repo['branch'].pop(0)

                URL = f"{base_URL}/{repo['user']}/{repo['repo']}/{ repo['branch'][0] }/{repo['file']}"
                response = client.get(URL)
                
                if response.status_code == 200:
                    text = response.text
                    return mistletoe.markdown(text), repo

                else:
                    print(f"repo's {URL} status code is {response.status_code}.\n",
                          f"double-check that all parameters are correct in the <tool .../> markup\n"
                          f"in the wiki article.")

                    print(f"{response.status_code} error => {[tool_key, repo]}") 
                    return False, False

    return False, False    


async def pre_process(article, wiki_page, article_wtp) -> str:
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

    # # -- naive regex to grab the <tool ... /> string
    # # as it is a custom DOM tag, it's not parsed and rendered
    # # properly into HTML so i can't easily parse it as HTML
    # # inside post_process
    # article_updated = re.sub(r"<tool(.*)/>", parse_tool_tag, article_wtp.string)
    # article_wtp.string = article_updated

    for template in article_wtp.templates:
        # save template value somewhere if needed
        # before running below code
        article['template'] = template.name.strip()
        del template[:]

    tasks = []
    for wikilink in article_wtp.wikilinks:

        # save category value somewhere if needed
        # before running below code
        if wikilink.title.lower().startswith('category:'):
            cat = wikilink.title.split(':')[-1]
            article['category'] = cat
            del wikilink[:]

        elif wikilink.title.lower().startswith('file:'):
            task = wiki_page.file_fetch(wikilink.title)
            tasks.append(asyncio.ensure_future(task))

        else:

            # -- convert normal wikilink to standard URL

            # TODO should decide if articles are organized in a tree
            # or not, and so construct the URL accordingly

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

                    task = wiki_page.file_fetch(f)
                    tasks.append(asyncio.ensure_future(task))

            tag.contents = '\n'.join(gallery_contents)

            await asyncio.gather(*tasks)
    

    # -- return article as string
    return article_wtp.string


def convert_rel_uri_to_abs(items, attr, repo):
    """
    replace each items relative URIs to an absolute one,
    using the specified attribute 
    """

    if len(items) > 0:
        with open("settings.toml", mode="rb") as f:
            config = tomli.load(f)

        for item in items:
            uri = item[attr]

            if not uri.startswith('http'):
                f = uri.split('/').pop()

                # -- handle URI to text files and binary files
                #    eg a.href and img.src
                #    <host>/<user>/<repo>/<blob?>/<branch>/<file>
                blob = ''
                base_URL = config['tool-plugin']['host'][repo['host']][0]

                if attr != 'src':
                    base_URL = config['tool-plugin']['host'][repo['host']][1]
                    blob = 'blob/'

                item[attr] = f"{base_URL}/{repo['user']}/{repo['repo']}/{blob}{repo['branch'][0]}/{f}"


def post_process(article: str, redirect_target: str | None = None):
    """
    update HTML before saving to disk:
    - add redirect text + link, if necessary
    - update wikilinks to set correct title attribute
    - replace Tool's wiki syntax to actual HTML
    - scan for a-href pointing to <https://hackersanddesigners.nl/...>
      and change them to be relative URLs?
    """

    soup = BeautifulSoup(article, 'lxml')

    # we insert some custom HTML to add a reference
    # that the current article has been moved to another URL
    if redirect_target is not None:
        redirect = f"<p>This page has been moved to <a href=\"{slugify(redirect_target)}.html\">{redirect_target}</a>.</p>"

        soup.body.insert(0, redirect)

    links = soup.find_all('a')
    for link in links:
        if 'title' in link.attrs:
            link.attrs['title'] = link.text

        # if link.attrs['href'].startswith('https://hackersanddesigners.nl'):
            # intercept abs-url pointing to root-level website
            # (eg https://hackersanddesigners.nl, no subdomain)
            # and re-write the URL to be in relative format
            # eg point to a page in *this* wiki

            # TODO: URL should be following new URL format,
            # design first new URL format

            # print('EXTERNAL LINK =>', urlparse(link.attrs['href']))
            # url_parse = urlparse(link.attrs['href'])
            # rel_url = url_parse.path
            # print('rel-url =>', rel_url)
            # link.attrs['href'] =

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
            convert_rel_uri_to_abs(links, 'href', repo)

            imgs = tool_soup.find_all('img')
            convert_rel_uri_to_abs(imgs, 'src', repo)

            # append updated tool_soup to the article's <body>
            # tk.parent => <p>; tk.parent.parent => <body>
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
    extract wiki template tags from article, if any
    """

    templates = article.templates

    if len(templates) > 0:

        for t in article.templates:
            label = t.name.strip()

            # collect all metadata from article.template table
            metadata = {}
            templates_keys = ['Name', 'Location', 'Date', 'Time', 'PeopleOrganisations', 'Type']
            for key in templates_keys:
                metadata[key.lower()] = get_metadata_field(t.get_arg(key))
    
            return metadata

    else:
        return None


def get_images(article):

    images = []
    for wikilink in article.wikilinks:
        if wikilink.title.lower().startswith('file:'):
            filename = wikilink.title[5:].strip()
            # TODO replace hardcoded path with env.MEDIA_DIR
            # and remove `/wiki/` from path
            filepath =  '/assets/media/' + filename

            images.append(filepath)

    return images
 

def get_category(wikilink):

    for wikilink in wikilink:
        if wikilink.title.lower().startswith('category:'):
            cat = wikilink.title.split(':')[-1]
            if cat is not None:
                return cat


async def parser(article: str, metadata_only: bool, redirect_target: str | None = None):
    """
    - instantiate WikiPage class
    - if redirect is not None, make custom HTML page
    - else, get page body (HTML)
    - return either version
    - return dict with article metadata to build index pages
    """

    print(f"parsing article {article['title']}...")

    wiki_page = WikiPage(article)
    wiki_page_errors = wiki_page.errors
    if len(wiki_page_errors) > 0:
        for error in wiki_page_errors:
            print('wiki-page err =>', error)

    wiki_article = wiki_page.page_load(article)

    if wiki_article is not None:

        article_wtp = wtp.parse(wiki_article)
        metadata = get_metadata(article_wtp)
        images = get_images(article_wtp)

        tool_metadata = None
        if metadata_only:

            category = get_category(article_wtp.wikilinks)
            if category == 'Tools':
                tool_metadata = get_tool_metadata(article_wtp.string)

            return metadata, images, tool_metadata

        wiki_body = await pre_process(article, wiki_page, article_wtp)

        # update wiki_article instance
        article['revisions'][0]['slots']['main']['content'] = wiki_body

        wiki_render = wiki_page.render()
        if len(wiki_render.errors) > 0:
            print(f":: wiki-page-render errors => {wiki_render.errors}")

        body_html = wiki_render.html
        body_html = post_process(body_html, redirect_target)

        print(f"parsed {article['title']}!")

        return body_html, metadata
