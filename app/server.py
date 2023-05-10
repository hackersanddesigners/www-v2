from dotenv import load_dotenv
import os
import traceback
import socket
import httpx
import json
from pretty_json_log import main as pretty_json_log
from template import get_template, make_url_slug, make_timestamp
from fetch import create_context
from build_article import make_article, redirect_article, save_article, delete_article
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

    filters = {
        'slug': make_url_slug,
        'ts': make_timestamp,
    }
    template = get_template('article', filters)
    sem = None
    context = create_context(ENV)

    async with httpx.AsyncClient(verify=context) as client: 

        while True:
            data, addr = server_sock.recvfrom(2048)
            msg = json.loads(data)
            pretty_json_log(msg)

            # -- we have the UPD message, let's read the operation
            #    type (new, edit, delete) and run appropriate function

            metadata_only = False

            if msg['type'] in ['new', 'edit']:
                try:
                    article_html, article_metadata = await make_article(msg['title'], client, metadata_only)
                    await save_article(article_html, template, sem)

                except Exception as e:
                    print(f"make-article err => {e}")
                    traceback.print_exc()

            elif msg['type'] == 'log':
                if msg['log_action'] == 'delete':
                    try:
                        await delete_article(msg['title'])

                    except Exception as e:
                        print(f"delete article err => {e}")
                        traceback.print_exc()

                elif msg['log_action'] == 'move':
                    try:
                        redirect = msg['log_params']

                        # no-redirect:
                        # - 0 => make redirect
                        # - 1 => no redirect
                        make_redirect = False
                        if redirect['noredir'] == '0':
                            make_redirect = True

                        if make_redirect:
                            source_article = await redirect_article(msg['title'], redirect['target'])
                            await save_article(source_article, template, sem)

                        target_article, target_metadata = await make_article(redirect['target'], client, metadata_only)
                        await save_article(target_article, template, sem)
                        

                    except Exception as e:
                        print(f"move article err => {e}")
                        traceback.print_exc()


if __name__ == '__main__':

    SERVER_IP = os.getenv('SERVER_IP')
    SERVER_PORT = int(os.getenv('SERVER_PORT'))
    ENV = os.getenv('ENV')

    asyncio.run(main(SERVER_IP, SERVER_PORT, ENV))
