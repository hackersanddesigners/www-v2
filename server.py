from dotenv import load_dotenv
import os
import traceback
import socket
import json
from slugify import slugify
from pretty_json_log import main as pretty_json_log
from jinja2 import Environment, FileSystemLoader
from fetch import fetch_article, article_exists
from parser import parser, WikiPage
import requests
from write_to_disk import main as write_to_disk
load_dotenv()


def main(SERVER_IP: str, SERVER_PORT: int):
    """
    - listen to UDP message coming from mediawiki instance at SERVER_PORT
    - fetch article by title using data from UDP message
    - parse article from wikitext and transform it to HTML
    """

    env = Environment(loader=FileSystemLoader('templates'), autoescape=True)

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_sock.bind((SERVER_IP, SERVER_PORT))

    print("UDP server has started and is ready to receive...",
          [SERVER_IP, SERVER_PORT])

    while True:
        data, addr = server_sock.recvfrom(2048)
        msg = json.loads(data)
        pretty_json_log(msg)

        # -- we have the UPD message, let's fetch the full article now
        try:
            page_title = msg['title']
            body_html = parser(page_title)

            article =  {
                "title": page_title,
                "html": body_html,
                "slug": slugify(page_title)
            }

            t = env.get_template('article.html')
            document = t.render(article=article)
            write_to_disk(article['slug'], document)

        except Exception as e:
            traceback.print_exc()


if __name__ == '__main__':

    SERVER_IP = os.getenv('SERVER_IP')
    SERVER_PORT = int(os.getenv('SERVER_PORT'))

    main(SERVER_IP, SERVER_PORT)
