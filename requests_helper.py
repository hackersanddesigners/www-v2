import requests
from requests import Request


def main(req_input, req_op, env: str):
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

        r = req_input.send(prepped, verify=False, stream=req_op['stream'])

    else:
        r = req_input.send(prepped, verify=True, stream=req_op['stream'])

    return r
