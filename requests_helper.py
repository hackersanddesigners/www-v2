import requests
from requests import Request


def main(req_input, req_op, env: str):
    """
    helper function to handle requests with no SSL check enabled.
    this func takes in:
    - request input (request)
    - request op (data w/ verb, url, params, etc)
    - app env (dev, prod) to disable SSL verification if
      running this program in a test environment
    """

    if req_op['verb'] == 'HEAD':
        req = Request(req_op['verb'],
                      url=req_op['url'])

    elif req_op['verb'] == 'GET':
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

        r = req_input.send(prepped, verify=False, stream=req_op['stream'])

    else:
        r = req_input.send(prepped, verify=True, stream=req_op['stream'])

    r.raise_for_status()

    return r


# refs:
# <https://www.mediawiki.org/wiki/API:Continue#Example_3:_Python_code_for_iterating_through_all_results>
# <https://github.com/nyurik/pywikiapi/blob/master/pywikiapi/Site.py#L259>
def query_continue(req_op, env):
    request = req_op['params']
    last_continue = {}

    while True:
        req = request.copy()
        req.update(last_continue)

        from urllib3.exceptions import InsecureRequestWarning
        # suppress only the single warning from urllib3 needed.
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

        response = requests.get(req_op['url'],
                                params=req,
                                verify=False).json()

        if 'warnings' in response:
            print(response['warnings'])
        if 'query' in response:
            yield response['query']
        if 'continue' not in response:
            print('query-continue over, break!')
            break

        last_continue = response['continue']
