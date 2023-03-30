from dotenv import load_dotenv
import os
import traceback
import socket
import httpx
import json
from pretty_json_log import main as pretty_json_log
# from jinja2 import Environment, FileSystemLoader
from templates import get_template
from fetch import create_context
from build_article import make_article, save_article
import asyncio
load_dotenv()


async def main(SERVER_IP: str, SERVER_PORT: int, ENV: str):
    """
    - listen to UDP message coming from mediawiki instance at SERVER_PORT
    - fetch article by title using data from UDP message
    - parse article from wikitext and transform it to HTML
    """

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_sock.bind((SERVER_IP, SERVER_PORT))

    print("UDP server has started and is ready to receive...",
          [SERVER_IP, SERVER_PORT])

    template = get_template('article', None)
    sem = None
    context = create_context(ENV)

    async with httpx.AsyncClient(verify=context) as client: 

        while True:
            data, addr = server_sock.recvfrom(2048)
            msg = json.loads(data)
            pretty_json_log(msg)

            # -- we have the UPD message, let's fetch the full article now
            try:
                article = await make_article(msg['title'], client)
                await save_article(article, template, sem)

            except Exception as e:
                print('make-article err =>', e)
                traceback.print_exc()


if __name__ == '__main__':

    SERVER_IP = os.getenv('SERVER_IP')
    SERVER_PORT = int(os.getenv('SERVER_PORT'))
    ENV = os.getenv('ENV')

    asyncio.run(main(SERVER_IP, SERVER_PORT, ENV))
