import sys
import os
import requests
from requests import Request, Session


def requests_helper(req_input, req_op, env: str):
    """
    helper function to handle requests with no SSL check enabled
    """

    if req_op['verb'] == 'GET':
        req = Request(req_op['verb'],
                      url=req_op['url'],
                      params=req_op['params'])

    elif req_op['verb'] == 'POST':
        req = Request(req_op['verb'],
                      url=req_op['url'],
                      data=req_op['params'])

    if req_op['session']:
        prepped = req_input.prepare_request(req)
    else:
        prepped = req.prepare()

    # <https://stackoverflow.com/a/32282390>
    # when working with local mediawiki and don't want
    # to issue SSL cert for it
    if env == 'dev':
        from urllib3.exceptions import InsecureRequestWarning
        # suppress only the single warning from urllib3 needed.
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

        r = req_input.send(prepped, verify=False)

    else:
        r = req_input.send(prepped, verify=True)

    return r


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
        'session': True
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
        'session': True
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
        'session': True
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
        'session': True
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
