from dotenv import load_dotenv
import sys
import os
import asyncio
import httpx
from requests_helper import create_context
load_dotenv()


async def main(ENV: str, input_page: str):
    """
    this func helps to test the whole workflow
    by triggering a change in a wiki article and
    let server.py do the rest.

    <https://www.mediawiki.org/wiki/API:Edit>
    login to the wikimedia instance as a bot user
    and update the given article (passed as arg)
    """

    URL = os.getenv('BASE_URL')
    BOT = {'usr': os.getenv('BOT_USR'), 'pwd': os.getenv('BOT_PWD')}

    context = create_context(ENV)
    async with httpx.AsyncClient(verify=context) as client: 

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


if __name__ == "__main__":

    ENV = os.getenv('ENV')
    input_page = None

    if (len(sys.argv) == 1):
        print("Missing argument: article URL to update")
        print("Eg run python make-changes-in-wiki.py <article-slug>")
        sys.exit(1)

    else:
        input_page = sys.argv[1]


    asyncio.run(main(ENV, input_page))
