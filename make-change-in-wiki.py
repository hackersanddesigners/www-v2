from dotenv import load_dotenv
import sys
import os
from requests import Session
from requests_helper import main as requests_helper
load_dotenv()


def main(env: str, input_page: str):
    """
    <https://www.mediawiki.org/wiki/API:Edit>
    login to the wikimedia instance as a bot user
    and update the given article (passed as arg)
    """

    s = Session()

    url = os.getenv('BASE_URL')
    bot = {'usr': os.getenv('BOT_USR'), 'pwd': os.getenv('BOT_PWD')}

    # GET request to fetch login token
    req_op_token = {
        'verb': 'GET',
        'url': url,
        'params': {
            'action': 'query',
            'meta': 'tokens',
            'type': 'login',
            'format': 'json'
        },
        'session': True,
        'stream': True
    }
    res_token = requests_helper(s, req_op_token, env)

    res_token_data = res_token.json()
    login_token = res_token_data['query']['tokens']['logintoken']

    # user bot credentials to log-in
    # make bot via `Special:BotPasswords`,
    # for `lgname`, `lgpassword`
    req_op_login = {
        'verb': 'POST',
        'url': url,
        'params': {
            'action': 'login',
            'lgname': bot['usr'],
            'lgpassword': bot['pwd'],
            'lgtoken': login_token,
            'format': 'json'
        },
        'session': True,
        'stream': True
    }

    requests_helper(s, req_op_login, env)

    # GET request to fetch CSRF token
    req_op_csrf = {
        'verb': 'GET',
        'url': url,
        'params': {
            'action': 'query',
            'meta': 'tokens',
            'format': 'json'
        },
        'session': True,
        'stream': True
    }

    res_csrf = requests_helper(s, req_op_csrf, env)
    res_csrf_data = res_csrf.json()
    csrf_token = res_csrf_data['query']['tokens']['csrftoken']

    # POST request to edit a page
    req_op_update = {
        'verb': 'POST',
        'url': url,
        'params': {
            'action': 'edit',
            'title': input_page,
            'token': csrf_token,
            'format': 'json',
            'appendtext': 'Hello'
        },
        'session': True,
        'stream': True
    }

    res_update = requests_helper(s, req_op_update, env)
    res_update_data = res_update.json()
    print('res POST req =>', res_update_data)

    # the POST request update the article and
    # send a message update to our server.py
    # which is listening for UDP datagrams


if __name__ == "__main__":

    env = os.getenv('ENV')
    input_page = None

    if (len(sys.argv) == 1):
        print("Missing argument: article URL to update")
        print("Eg run python make-changes-in-wiki.py <article-slug>")
        sys.exit(1)

    else:
        input_page = sys.argv[1]

    main(env, input_page)
