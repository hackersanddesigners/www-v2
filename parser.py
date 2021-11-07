from wikitexthtml import Page
import wikitextparser as wtp
from slugify import slugify

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
        return

    def clean_url(self, url):
        """Clean "url" (which is a wikilink) to become a valid URL to call."""
        return

    def clean_title(self, title):
        """Clean "title" (which is a full pagename) to become more human readable."""
        return

    def file_get_link(self, url):
        """Get the link to a file (for the "a href" of the File)."""
        return url

    def file_get_img(self, url, thumb):
        """Get the "img src" to a file. If thumb is set, a thumb should be generated of that size."""
        print('file_get_img =>', [self, url, thumb])
        return

def parser(data):
    article_data = data['query']['pages'][0]
    article = {
        'title': article_data['title'],
        'id': article_data['pageid'],
        'slug': slugify(article_data['title']),
        'body': article_data['revisions'][0]['slots']['main']['content'],
        'template': None,
        'category': None,
        'html': None
    }

    article = pre_process(article)

    wiki_page = WikiPage(article)
    body_html = wiki_page.render().html
    article['html'] = body_html

    # print(body_html)

    return article


def pre_process(article):
    """We take out any {{template}} and [[category:<>]] syntax, before rendering the article"""

    article_wtp = wtp.parse(article['body'])

    for template in article_wtp.templates:
        article['template'] = template.name.strip()
        del template[:]

    for wikilink in article_wtp.wikilinks:
        if wikilink.title.lower().startswith('category:'):
            cat = wikilink.title.split(':')[-1]
            article['category'] = cat 
            del wikilink[:]

    article['body'] = article_wtp.string

    return article
