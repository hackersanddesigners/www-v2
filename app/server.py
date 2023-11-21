from dotenv import load_dotenv
import os
import traceback
import socket
import httpx
import json
from app.pretty_json_log import main as pretty_json_log
from app.views.views import (
    get_template,
)
from app.views.template_utils import (
    make_url_slug,
    make_timestamp
)
from app.fetch import create_context
from app.build_article import (
    make_article,
    redirect_article,
    save_article,
    delete_article,
)
from app.build_category_index import make_category_index
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

    print(f"UDP server has started and is ready to receive...",
          f"{SERVER_IP, SERVER_PORT}")

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

            # namespace: -1 is part of Special Pages, we don't parse those
            if msg['namespace'] == -1:
                return

            # filter out `Concept:<title>` articles
            if msg['title'].startswith("Concept:"):
                return

            if (msg['type'] in ['new', 'edit']
                or msg['type'] == 'log'
                and msg['log_action'] in ['restore', 'delete_redir']):

                try:
                    article_list = []

                    # article is a tuple in the form: (article_html, article_metadata)
                    article = await make_article(msg['title'], client, metadata_only)
                    if article is None:
                        return

                    article_list.append(article)

                    if len(article[1]['translations']) > 0:
                        art_tasks = []
                        for translation in article[1]['translations']:
                            trans_task = make_article(translation, client, metadata_only)
                            art_tasks.append(asyncio.ensure_future(trans_task))

                        prepared_articles = await asyncio.gather(*art_tasks)
                        article_list.extend(prepared_articles)

                    # -- update every category index page the article has
                    cat_tasks = []
                    for cat in article[1]['metadata']['categories']:
                        task = make_category_index(cat)
                        cat_tasks.append(asyncio.ensure_future(task))

                    prepared_category_indexes = await asyncio.gather(*cat_tasks)
                    print(f"prepared_category_indexes :: {prepared_category_indexes}")
                    prepared_category_indexes = [item for item
                                                 in prepared_category_indexes
                                                 if item is not None]

                    cat_tasks_html = []
                    for cat_index in prepared_category_indexes:
                        filepath = f"{cat_index['slug']}"
                        task = save_article(cat_index, filepath, template, sem)
                        cat_tasks_html.append(asyncio.ensure_future(task))

                    await asyncio.gather(*cat_tasks_html)
                    # --

                    # -- write article to disk
                    for article in article_list:
                        filepath = f"{article[0]['slug']}"
                        await save_article(article[0], filepath, template, sem)

                except Exception as e:
                    print(f"make-article err ({msg['title']}) => {e}")
                    traceback.print_exc()

            elif msg['type'] == 'log':

                if msg['log_type'] == 'delete':

                    if msg['log_action'] == 'delete':
                        try:
                            await delete_article(msg['title'])

                        except Exception as e:
                            print(f"delete article err => {e}")
                            traceback.print_exc()

                elif msg['log_type'] == 'move':
                    
                    if msg['log_action'] in ['move', 'delete_redir']:
                        try:
                            redirect = msg['log_params']

                            # no-redirect:
                            # - 0 => make redirect
                            # - 1 => no redirect
                            make_redirect = False
                            if 'noredir' in redirect and redirect['noredir'] == '0':
                                make_redirect = True

                            target_html, target_metadata = await make_article(redirect['target'], client, metadata_only)
                            target_category = target_metadata['metadata']['category']
                            target_filepath = f"{target_category}/{target_html['slug']}"

                            if make_redirect:
                                source_article, source_metadata = await make_article(msg['title'], client, metadata_only)
                                source_filepath = await redirect_article(msg['title'], redirect['target'])
                                await save_article(source_article, source_filepath, template, sem)

                            await save_article(target_html, target_filepath, template, sem)


                        except Exception as e:
                            print(f"move article err => {e}")
                            traceback.print_exc()

            else:
                print(f"we dont' know how to parse this MW operation.")


if __name__ == '__main__':

    SERVER_IP = os.getenv('SERVER_IP')
    SERVER_PORT = int(os.getenv('SERVER_PORT'))
    ENV = os.getenv('ENV')

    asyncio.run(main(SERVER_IP, SERVER_PORT, ENV))
