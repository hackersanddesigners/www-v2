import sys
import socket
import json
import requests
import wikitextparser as wtp
from wikitexthtml import Page
from jinja2 import Environment, FileSystemLoader
from slugify import slugify

env = Environment(loader=FileSystemLoader('templates'), autoescape=True)

# ---
SERVER_IP = "localhost"
SERVER_PORT = 1338

server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_sock.bind((SERVER_IP, SERVER_PORT))

print("UDP server has started and is ready to receive")
# ---

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


def read_file(filepath):
    with open(filepath, 'r') as f:
        try:
            content = f.read()
            return content
            
        except Exception as e:
            print('✕ error (parse) for article "%s" =>' % filepath, e)


# input_path = 'test-article.wikitext'
# content = read_file(input_path)
# article = {
#     'title': 'Test Page',
#     'id': 10202020,
#     'slug': 'test-page',
#     'body': content
# }
# wiki_page = WikiPage(article)
# print(wiki_page.render().html)

while True:
    data, addr = server_sock.recvfrom(2048)
    msg = json.loads(data)
    print('msg =>', json.dumps(msg, indent=4))

    #-- we have the UPD message, let's fetch the full article now
    # base_url = 'https://wiki.hackersanddesigners.nl/api.php?'
    base_url = 'http://hd-mw.test/api.php?'

    # action=query&
    # prop=revisions&
    # titles=AntiSpoof&
    # formatversion=2&
    # redirects=1

    options = {'action': 'query',
               'prop': 'revisions',
               'titles': msg['title'],
               'rvprop': 'content',
               'rvslots': '*',
               'formatversion': '2',
               'format': 'json',
               'redirects': '1'}

    response = requests.get(base_url, params=options)
    try: 
        data = response.json()

        article_data = data['query']['pages'][0]

        article = {
            'title': article_data['title'],
            'id': article_data['pageid'],
            'slug': slugify(article_data['title']),
            'body': article_data['revisions'][0]['slots']['main']['content'],
            'html': None
        }

        page_parsed = wtp.parse(article_data['revisions'][0]['slots']['main']['content']) 

        for t in page_parsed.templates:
            print('PP TEMPLATE =>', t.name.strip())
            template = t

        wiki_page = WikiPage(article)
        name = template.name.strip()
        body = wiki_page.template_load(name)

        body_html = wiki_page.render().html
        print(body_html)

        article['html'] = body_html

        t = env.get_template('article.html')
        document = t.render(article=article)

        with open('./wiki/%s.html' % article['slug'], 'w') as f:
            try:
                f.write(document)
                print('✓ %s-article "%s" has been correctly written to disk' % (article['slug'], article['title']))
            except Exception as e:
                print('✕ error for %s-article "%s" =>' % (article['slug'], article['title']), e)

    except Exception as e:
        print('ERR ARTICLE =>', e)
