from dotenv import load_dotenv
import os
from typing import Optional
from wikitexthtml import Page
import wikitextparser as wtp
from fetch import article_exists, fetch_file, file_exists
from slugify import slugify
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import asyncio
load_dotenv()


class WikiPage(Page):

    MEDIA_DIR = os.getenv('MEDIA_DIR')

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

        # return article_exists(page)
        return

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
        - first we check if the file exists already on disk
        - else we try to fetch it down and return if it succeeded or not
        """

        # we're doing our checks directly in file_fetch
        # return file_exists(file)
        return

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

        # print('clean-title =>', [self, title])
        # do we use this? set it anyway for "future-proofness" / archeology
        return title

    def file_get_link(self, url: str) -> str:
        """
        Get the link to a file (for the "a href" of the File).
        """

        return f"/{self.MEDIA_DIR}/{url}"

    def file_get_img(self, url: str, thumb: Optional[int] = None) -> str:
        """
        Get the "img src" to a file.
        If thumb is set, a thumb should be generated of that size.
        """

        return f"/{self.MEDIA_DIR}/{url}"


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

            wikilink.text = wikilink.text or wikilink.target

    await asyncio.gather(*tasks)

    for tag in article_wtp.get_tags():

        # TODO: scan through all wiki articles
        # and save in db all tags as tag.name + tag.contents
        # then check which ones are often malformed / needs care;
        #
        # make sure syntax is "strict"
        # eg image syntax starts with `File:<filepath>`
        # note: if a filepath is malformed and we know it
        # does not exists in the wiki, what to do?
        #   => must be updated in the wiki; we don't try to fix
        #   wiki content on-the-fly

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

    return article_wtp.string


def post_process(article: str, redirect_target: str | None = None):
    """
    update HTML before saving to disk:
    - add redirect text + link, if necessary
    - update wikilinks to set correct title attribute
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
            filepath =  '/assets/media/' + filename

            images.append(filepath)

    return images
 

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

        if metadata_only:
            return metadata, images

        wiki_body = await pre_process(article, wiki_page, article_wtp)

        # update wiki_article instance
        article['revisions'][0]['slots']['main']['content'] = wiki_body

        body_html = wiki_page.render().html
        body_html = post_process(body_html, redirect_target)

        print(f"parsed {article['title']}!")


        return body_html, metadata
