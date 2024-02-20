from dotenv import load_dotenv
import os
import traceback
import socket
import httpx
import json
from app.pretty_json_log import main as pretty_json_log
from app.views.template_utils import (
    get_template,
    make_url_slug,
    make_timestamp
)
from app.fetch import (
    create_context,
    convert_article_trans_title_to_regular_title,
)
from app.build_article import (
    make_article,
    make_redirect_article,
    save_article,
    delete_article,
    remove_article_traces,
    update_backlinks,
)
from app.build_category_index import (
    update_categories
)
from app.build_front_index import (
    build_front_index
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

            # -- check if article is a snippet translation
            #    eg `<title>/<num-version>/<lang>
            #    and instead convert Title to regular article
            #    so we updated it, instead of ignorin the
            #    translation snippet.
            msg['title'] = convert_article_trans_title_to_regular_title(msg['title'])

            if (msg['type'] in ['new', 'edit']
                or msg['type'] == 'log'
                and msg['log_action'] in ['restore', 'delete_redir']):

                try:
                    article = await make_article(msg['title'], client)

                    if not article:
                        print(f"server :: new / edit op: no article found\n"
                              f"  for => {msg['title']}")

                    else:
                        # -- update every category index page the article has
                        #    and write it to disk
                        # -- update article backlinks
                        await update_categories(article, sem)
                        await update_backlinks(article, sem)

                        # update front-index if necessary
                        art_title = article['title']
                        art_cats = article['metadata']['categories']
                        await build_front_index(art_title, art_cats)

                        # -- write article to disk
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
                            await remove_article_traces(msg['title'])

                            # update front-index if necessary
                            art_title = msg['title']
                            art_cats = None
                            await build_front_index(art_title, art_cats)


                        except Exception as e:
                            print(f"delete article err => {e}")
                            traceback.print_exc()

                elif msg['log_type'] == 'move':

                    # we honor user's preference in the MW Move Article page:
                    # if leave redirect behind is toggled, we leave the previous page
                    # else we remove it, including any URL traces across the wiki

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
                            await update_categories(target, sem)

                            # update front-index if necessary
                            art_title = target['title']
                            art_cats = target['metadata']['categories']
                            await build_front_index(art_title, art_cats)

                            if make_redirect:
                                target_redirect = {
                                    'title': target['title'],
                                    'slug': target['slug']
                                }

                                await make_redirect_article(msg['title'], target_redirect)
                                
                            else:
                                await delete_article(msg['title'])
                                await remove_article_traces(msg['title'])
                                

                            await save_article(target, target['slug'], template, sem)
                            

                        except Exception as e:
                            print(f"move article err => {e}")
                            traceback.print_exc()

            else:
                print(f"we dont' know how to parse this MW operation.",
                      f"=> {msg}")


if __name__ == '__main__':

    SERVER_IP = os.getenv('SERVER_IP')
    SERVER_PORT = int(os.getenv('SERVER_PORT'))
    ENV = os.getenv('ENV')

    asyncio.run(main(SERVER_IP, SERVER_PORT, ENV))
