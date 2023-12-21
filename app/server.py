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
from app.build_category_index import (
    update_categories,
)
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

    template = get_template('article')
    sem = None
    context = create_context(ENV)

    async with httpx.AsyncClient(verify=context) as client:

        while True:
            data, addr = server_sock.recvfrom(2048)
            msg = json.loads(data)
            pretty_json_log(msg)

            # -- we have the UPD message, let's read the operation
            #    type (new, edit, delete) and run appropriate function

            # namespace: -1 is part of Special Pages, we don't parse those
            if msg['namespace'] == -1:
                return

            # filter out `Concept:<title>` articles
            if msg['title'].startswith("Concept:"):
                return

            # filter our `Special:<title>` articles
            if msg['title'].startswith("Special:"):
                return

            if (msg['type'] in ['new', 'edit']
                or msg['type'] == 'log'
                and msg['log_action'] in ['restore', 'delete_redir']):

                try:
                    article_list = []

                    # article is a tuple in the form: (article_html, article_metadata)
                    article = await make_article(msg['title'], client)

                    # print( json.dumps( article, indent=2 ) )

                    if not article:
                        return

                    # TODO if we remove below code for translations,
                    # we don't need to append article to the list and
                    # loop over it. update_categories handles its own
                    # async iterator to write HTML to disk (unless we
                    # find a better way to run just one async iterator)
                    # thing is we need to `await make_article()` above
                    # immediately, before handling collateral article's
                    # functions like translaions, categories update, etc
                    # since if article returns None, we stop everything
                    # right there.
                    article_list.append(article)

                    # -- make article translations articles
                    # if len(article[1]['translations']) > 0:
                    #     art_tasks = []
                    #     for translation in article[1]['translations']:
                    #         trans_task = make_article(translation, client, metadata_only)
                    #         art_tasks.append(asyncio.ensure_future(trans_task))

                    #     prepared_articles = await asyncio.gather(*art_tasks)
                    #     article_list.extend(prepared_articles)

                    # -- update every category index page the article has
                    #    and write it to disk
                    await update_categories(article, template, sem)

                    # -- write article to disk
                    for article in article_list:
                        filepath = f"{article['slug']}"
                        await save_article(article, filepath, template, sem)

                except Exception as e:
                    print(f"make-article err ({msg['title']}) => {e}")
                    traceback.print_exc()

            elif msg['type'] == 'log':

                if msg['log_type'] == 'delete':

                    if msg['log_action'] == 'delete':
                        try:
                            await delete_article(msg['title'])

                            # -- TODO scan all category index HTML templates
                            #    with bs4 and remove any block + link pointing
                            #    to article removed just above.

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

                            target = await make_article(redirect['target'], client)

                            if make_redirect:
                                source = await make_article(msg['title'], client)
                                source_filepath = await redirect_article(msg['title'], redirect['target'])
                                await save_article(source, source_filepath, template, sem)

                            await save_article(target, target['slug'], template, sem)

                            await update_categories(target, template, sem)

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
