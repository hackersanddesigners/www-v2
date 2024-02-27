import asyncio
import os
import sys

import httpx
from dotenv import load_dotenv

from app.fetch import create_context

load_dotenv()


async def get_csrf_token(URL: str, client) -> str:
    """
    login to the wikimedia instance as a bot user
    and return CSRF token to use for other MW operations
    <https://www.mediawiki.org/wiki/API:Edit>
    """

    BOT = {'usr': os.getenv('BOT_USR'), 'pwd': os.getenv('BOT_PWD')}

    # GET request to fetch login token
    params_token = {
        'action': 'query',
        'meta': 'tokens',
        'type': 'login',
        'formatversion': '2',
        'format': 'json'
    }
    res_token = await client.get(URL, params=params_token)
    res_token_data = res_token.json()
    login_token = res_token_data['query']['tokens']['logintoken']
    
    # user bot credentials to log-in
    # make bot via `Special:BotPasswords`,
    # for `lgname`, `lgpassword`
    params_login = {
        'action': 'login',
        'lgname': BOT['usr'],
        'lgpassword': BOT['pwd'],
        'lgtoken': login_token,
        'formatversion': '2',
        'format': 'json'
    }

    await client.post(URL, data=params_login)

    # GET request to fetch CSRF token
    params_csrf = {
        'action': 'query',
        'meta': 'tokens',
        'formatversion': '2',
        'format': 'json'
    }

    res_csrf = await client.get(URL, params=params_csrf)
    res_csrf_data = res_csrf.json()
    csrf_token = res_csrf_data['query']['tokens']['csrftoken']

    return csrf_token


async def create_edit_page(URL: str, input_page: str, client):
    """
    this func create a new article or edit an existing one.

    <https://www.mediawiki.org/wiki/API:Edit>
    login to the wikimedia instance as a bot user
    and update the given article (passed as arg)
    """

    csrf_token = await get_csrf_token(URL, client)

    # POST request to edit a page
    params_update = {
        'action': 'edit',
        'title': input_page,
        'token': csrf_token,
        'format': 'json',
        'appendtext': 'Hello'
       }

    res_update = await client.post(URL, data=params_update)
    res_update_data = res_update.json()
    print('res POST req =>', res_update_data)

    # the POST request update the article and
    # send a message update to our server.py
    # which is listening for UDP datagrams


async def delete_page(URL, input_page, client):
    """
    this func delete an existing wiki article
    <https://www.mediawiki.org/wiki/API:Delete>
    """

    csrf_token = await get_csrf_token(URL, client)

    # POST request to edit a page
    params_update = {
        'action': 'delete',
        'title': input_page,
        'token': csrf_token,
        'format': 'json',
        'reason': 'test had.py v2 APIs'
    }

    res_update = await client.post(URL, data=params_update)
    res_update_data = res_update.json()
    print('res POST req =>', res_update_data)


async def main(ENV: str, URL: str, input_page: str, operation: str):
    """
    set of functions to test the whole build / update workflow
    by creating, updating or deleting a wiki article;
    this lets server.py do the rest.
    """

    context = create_context(ENV)
    async with httpx.AsyncClient(verify=context) as client:

        if operation == 'edit':
            await create_edit_page(URL, input_page, client)

        elif operation == 'delete':
            await delete_page(URL, input_page, client)


if __name__ == "__main__":

    ENV = os.getenv('ENV')
    URL = os.getenv('BASE_URL')

    input_page = None
    operation = None

    if (len(sys.argv) < 2):
        print("Missing argument: either article URL to work with or API operation")
        print("Eg run python make-changes-in-wiki.py <article-slug> <edit / delete>")
        sys.exit(1)

    else:
        input_page = sys.argv[1]
        operation = sys.argv[2]


    asyncio.run(main(ENV, URL, input_page, operation))
