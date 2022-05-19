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


    print('article (parsed) =>', json.dumps(article, indent=2))

    return article


def pre_process(article):
    """We take out any {{template}} and [[category:<>]] syntax,
    before rendering the article. We also update wikilinks [[<>]] to point to
    correct locations, so that WikiTextParser does its job just fine."""

    article_wtp = wtp.parse(article['body'])

    # print('article_wtp =>', article_wtp, '\n---\n')

    for template in article_wtp.templates:
        # print('article_wtp template =>', article['template'], '\n---\n')
        article['template'] = template.name.strip()
        del template[:]

    # print('wikilinks =>', article_wtp.wikilinks)
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

            # print('file-data =>', file_data)
            wikilink.title = "File:%s|%s" % (file_data['url'], file_data['caption'])

        else:
            # convert normal wikilink to standard URL
            # print('wikilink page =>', wikilink.title)

            # TODO should decide if articles are organized in a tree
            # or not, and so construct the URL accordingly
            article_url = slugify(wikilink.title)

            wikilink.title = article_url


        # TODO scan through all <a href> and intercept those
        # pointing to <https://hackersanddesigners.nl> ?



    article['body'] = article_wtp.string

    return article
