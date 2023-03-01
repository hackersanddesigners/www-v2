from typing import Optional
from wikitexthtml import Page
import wikitextparser as wtp
from fetch import article_exists, fetch_article, fetch_file
from slugify import slugify
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse


class WikiPage(Page):
    def page_load(self, page: str) -> str:
        """
        Load the page indicated by "page" and return its body.
        """
        data = fetch_article(page)
        article_data = data['query']['pages'][0]
        return article_data['revisions'][0]['slots']['main']['content']

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
        print('file-exists =>', [self, file])
        # add func to fetch file part of an article
        data = fetch_file(file)
        return file

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

        # return correct file path format
        return url

    def file_get_img(self, url: str, thumb: Optional[int] = None) -> str:
        """
        Get the "img src" to a file.
        If thumb is set, a thumb should be generated of that size.
        """
        print('file-get-img =>', [self, url, thumb])

        # return correct file path format
        return url


def parser(data):
    article_data = data['query']['pages'][0]


    test_gallery_html_1 = """<gallery caption="Sample gallery" widths="100px" heights="100px" perrow="6">
File:Drenthe-Position.png|[[w:Drenthe|Drenthe]], the least crowded province
File:Flevoland-Position.png
File:Friesland-Position.png|[[w:Friesland|Friesland]] has many lakes
File:Gelderland-Position.png
File:Groningen-Position.png
File:Limburg-Position.png
File:Noord_Brabant-Position.png
File:Noord_Holland-Position.png
Overijssel-Position.png
Utrecht-Position.png
Zuid_Holland-Position.png|[[w:South Holland|South Holland]], the most crowded province
Zeeland-Position.png|link=nl:Zeeland (provincie)
</gallery>"""

    test_gallery_html_2 = """<gallery mode=packed>
Example.jpg|example of normal length caption maybe
Line_sensor.JPG
Example.jpg|example of normal length caption maybe
</gallery>"""

    # TODO we've ended up converting article['body'] to HTML
    # using wikitextothtml, therefore keeping fields
    # like `files` seems unnecessary?
    article = {
        'title': article_data['title'],
        'id': article_data['pageid'],
        'slug': slugify(article_data['title']),
        'body': article_data['revisions'][0]['slots']['main']['content'],
        'files': [],
        'template': None,
        'category': None,
        'html': None
    }

    article = pre_process(article)
    wiki_page = WikiPage(article)

    body_html = wiki_page.render().html
    body_html = post_process(body_html)
    article['html'] = body_html

    # print('article (parsed) =>', json.dumps(article, indent=2))

    return article


def pre_process(article):
    """We take out any {{template}} and [[category:<>]] syntax,
    before rendering the article. We also update wikilinks [[<>]] to point to
    correct locations, so that WikiTextParser does its job just fine."""

    article_wtp = wtp.parse(article['body'])

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
            # download file to disk and fetch metadata
            # print('wikilink file =>', wikilink.title)

            title = wikilink.title
            file_data = fetch_file(title)
            article['files'].append(file_data)

            wikilink.title = "File:%s|%s" % (file_data['url'], file_data['caption'])

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
            # link to in the format `title-of-page.html` so if we live
            # the link style like this, the page will never be found.

            wl_label = wikilink.target
            # TODO wikilink.title is set to be wikilink.target when using
            # wikitextohtml, so we need to run a post-process function
            
            wikilink.title = wl_label
            wikilink.text = wikilink.text or wl_label
            wikilink.target = article_url 


    # save pre-processed wikitext article to `body`
    article['body'] = article_wtp.string

    # return updated article dictionary
    return article


def post_process(article):
    """
    update HTML before saving to disk:
    - update wikilinks to set correct title attribute
    - scan for a-href pointing to <https://hackersanddesigners.nl/...> and change them to be relative URLs?
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

            print('EXTERNAL LINK =>', urlparse(link.attrs['href']))
            url_parse = urlparse(link.attrs['href'])
            rel_url = url_parse.path
            print('rel-url =>', rel_url)
            # link.attrs['href'] = 


    return soup.prettify()
    
