from wikitexthtml import Page
import wikitextparser as wtp
from fetch import fetch_article, fetch_file
from slugify import slugify
import json


class WikiPage(Page):
    def __init__(self, page):
        super().__init__(page)
        self.en_page = None
        self.categories = []

    def page_load(self, page):
        """Load the page indicated by "page" and return its body."""
        return page['body']

    def page_exists(self, page):
        """Return True if and only if the page exists."""
        return

    def template_load(self, template):
        """Load the template indicated by "template" and return its body."""
        return template

    def template_exists(self, template):
        """Return True if and only if the template exists."""
        return

    def file_exists(self, file):
        """Return True if and only if the file (upload) exists."""
        return file

    def clean_url(self, url):
        """Clean "url" (which is a wikilink) to become a valid URL to call."""
        # print('clean-url =>', url)
        return url

    def clean_title(self, title):
        """Clean "title" (which is a full pagename) to become more human readable."""
        # print('clean-title =>', title)
        return title

    def file_get_link(self, url):
        """Get the link to a file (for the "a href" of the File)."""
        # print('file-get-link =>', url)
        return url

    def file_get_img(self, url, thumb):
        """Get the "img src" to a file. If thumb is set, a thumb should be generated of that size."""
        # print('file-get-img =>', [self, url, thumb])

        return url


def parser(data):
    article_data = data['query']['pages'][0]
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

        print('wikilink =>', wikilink)

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

            print('wikilink.title =>', [wikilink.title, wl_label])


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
