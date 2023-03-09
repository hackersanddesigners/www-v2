from dotenv import load_dotenv
import os
from typing import Optional
from wikitexthtml import Page
import wikitextparser as wtp
from fetch import article_exists, fetch_article, fetch_file, file_exists
from slugify import slugify
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from pretty_json_log import main as pretty_json_log
load_dotenv()



MEDIA_DIR = '/'.join(os.getenv('MEDIA_DIR').split('/')[2:])

class WikiPage(Page):

    def page_load(self, page) -> str:
        """
        Load the page indicated by "page" and return its body.
        """
        return page['revisions'][0]['slots']['main']['content']

    def page_exists(self, page: str) -> bool:
        """
        Return True if and only if the page exists.
        """
        return article_exists(page)

    def template_load(self, template: str) -> str:
        """
        Load the template indicated by "template" and return its body.
        """
        print('template-load =>', [self, template])
        # do we use templates?
        return template

    def template_exists(self, template: str) -> bool:
        """
        Return True if and only if the template exists.
        """
        print('template-exists =>', [self, template])
        # see above
        return

    def file_exists(self, file: str) -> bool:
        """
        Return True if and only if the file (upload) exists:
        - first we check if the file exists already on disk
        - else we try to fetch it down and return if it succeeded or not
        """
        return file_exists(file)

    def file_fetch(self, file: str) -> bool:
        """
        Fetch the file indicated by "file" and save it to disk,
        only if a newer version of the one already saved to disk exists
        (we use timestamps between local and upstream file for this)
        """

        return fetch_file(file)

    def clean_url(self, url: str) -> str:
        """
        Clean "url" (which is a wikilink) to become a valid URL to call.
        """
        print('clean-url =>', [self, url])
        # put func that clean up href between internal and external?
        return url

    def clean_title(self, title: str) -> str:
        """
        Clean "title" (which is a full pagename) to become more human readable.
        """
        print('clean-title =>', [self, title])
        # do we use this? set it anyway for "future-proofness" / archeology
        return title

    def file_get_link(self, url: str) -> str:
        """
        Get the link to a file (for the "a href" of the File).
        """
        print('file-get-link =>', [self, url])

        return f"{MEDIA_DIR}/{url}"

    def file_get_img(self, url: str, thumb: Optional[int] = None) -> str:
        """
        Get the "img src" to a file.
        If thumb is set, a thumb should be generated of that size.
        """
        print('file-get-img =>', [self, url, thumb])

        return f"{MEDIA_DIR}/{url}"


def parser(page_title: str):
    """
    - fetch article from MW APIs
    - instantiate WikiPage class
    - get page body (HTML) and return it
    """
    
    article = fetch_article(page_title)

    wiki_page = WikiPage(article)
    wiki_page_errors = wiki_page.errors
    if len(wiki_page_errors) > 0:
        for error in wiki_page_errors:
            print('wiki-page err =>', error)

    wiki_article = wiki_page.page_load(article)
    pre_process(article, wiki_article)

    for image in article['images']:
       image_file = wiki_page.file_fetch(image['title'])

    body_html = wiki_page.render().html
    body_html = post_process(body_html)

    return body_html


def pre_process(article, body: str):
    """
    - TODO if now we change in place, this needs to be adjusted
      parse, save elsewhere and take out any {{template}}
      and [[category:<>]] syntax, before rendering the article.
    - update wikilinks [[<>]] to point to correct locations,
      so that WikiTextParser does its job just fine.
    - check for any malformed (and known / used) wiki tags,
      for instance the gallery tag: either try to fix it
      (if knowning how), or else report it somewhere so that
      the wiki article can be fixed instead
    """

    # body = article['revisions'][0]['slots']['main']['content']
    article_wtp = wtp.parse(body)

    # <2022-10-13> as we are in the process of "designing our own TOC"
    # we need to inject `__NOTOC__` to every article to avoid
    # wikitexthtml to create a TOC
    article_wtp.insert(0, '__NOTOC__')

    for template in article_wtp.templates:
        article['template'] = template.name.strip()
        del template[:]

    for wikilink in article_wtp.wikilinks:

        if wikilink.title.lower().startswith('category:'):
            cat = wikilink.title.split(':')[-1]
            article['category'] = cat
            del wikilink[:]

        elif wikilink.title.lower().startswith('file:'):
            print('wikilink file =>', wikilink)

            # title = wikilink.title

            # wikilink.title = "File:%s|%s" % (file_data['url'],
            #                                  file_data['caption'])

        else:
            # convert normal wikilink to standard URL

            # TODO should decide if articles are organized in a tree
            # or not, and so construct the URL accordingly
            article_url = slugify(wikilink.title)

            # most times only a wikilink like this is added:
            # [Title of Other Page]
            # and Mediawiki automatically converts that into a proper URL
            # so we set wikilink.target to wikilink.title and wikilink.text
            # *then* we update wikilink.target to the slugified URL version
            # the main problem here is that we slugify all HTML pages we
            # link to in the format `title-of-page.html` so if we leave
            # the link style like this, the page will never be found.

            wl_label = wikilink.target
            # TODO wikilink.title is set to be wikilink.target when using
            # wikitextohtml, so we need to run a post-process function

            wikilink.title = wl_label
            wikilink.text = wikilink.text or wl_label
            wikilink.target = article_url

    print('article tags =>', article_wtp.get_tags())
    for tag in article_wtp.get_tags():

        # TODO: scan through all wiki articles
        # and save in db all tags as tag.name + tag.contents
        # then check which ones are often malformed / needs care

        # make sure syntax is "strict"
        # eg image syntax starts with `File:<filepath>`
        # TODO: if a filepath is malformed and we know it
        # does not exists in the wiki, what to do?
        if tag.name == 'gallery':
            gallery_files = tag.contents.split('\n')
            gallery_files = [f.strip() for f in gallery_files if f]

            gallery_contents = []
            for gallery_f in gallery_files:
                if not gallery_f.startswith('File:'):
                    print('gallery file bad syntax =>', gallery_f)
                    f = 'File:' + gallery_f
                    gallery_contents.append(f)

            tag.contents = '\n'.join(gallery_contents)
            print('updated gallery tag =>', tag)

    # update wiki_article instance
    article['revisions'][0]['slots']['main']['content'] = article_wtp.string


def post_process(article):
    """
    update HTML before saving to disk:
    - update wikilinks to set correct title attribute
    - scan for a-href pointing to <https://hackersanddesigners.nl/...>
      and change them to be relative URLs?
    """

    soup = BeautifulSoup(article, 'lxml')
    links = soup.find_all('a')

    for link in links:
        if 'title' in link.attrs:
            link.attrs['title'] = link.text

        if link.attrs['href'].startswith('https://hackersanddesigners.nl'):
            # intercept abs-url pointing to root-level website
            # (eg https://hackersanddesigners.nl, no subdomain)
            # and re-write the URL to be in relative format
            # TODO: URL should be following new URL format

            # print('EXTERNAL LINK =>', urlparse(link.attrs['href']))
            url_parse = urlparse(link.attrs['href'])
            rel_url = url_parse.path
            # print('rel-url =>', rel_url)
            # link.attrs['href'] =

    return soup.prettify()
