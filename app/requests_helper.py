from dotenv import load_dotenv
import os
from pathlib import Path
import httpx
load_dotenv()


def create_context(ENV):
    if ENV == 'dev':
        base_dir = Path(__file__).parent.parent
        import ssl
        context = ssl.create_default_context()
        LOCAL_CA = os.getenv('LOCAL_CA')
        context.load_verify_locations(cafile=f"{base_dir}/{LOCAL_CA}")

        return context

    else:
        # True use default CA bundle
        return True


async def main(client, req_op):
    """
    helper function to handle requests with no SSL check enabled.
    this func takes in:
    - request input (client)
    - request op (data w/ verb, url, params, etc)
    """

    if req_op['verb'] == 'HEAD':
        req = httpx.Request(req_op['verb'],
                            url=req_op['url'])

    elif req_op['verb'] == 'GET':
        req = httpx.Request(req_op['verb'],
                            url=req_op['url'],
                            params=req_op['params'])

    elif req_op['verb'] == 'POST':
        req = httpx.Request(req_op['verb'],
                            url=req_op['url'],
                            data=req_op['params'])

    if req_op['stream']:
        req = httpx.Request(req_op['verb'], url=req_op['url'])
        httpx.stream(req)

    else:
        r = await client.send(req)

    r.raise_for_status()

    print('r =>', [r, r.raise_for_status()])
    return r


# refs:
# <https://www.mediawiki.org/wiki/API:Continue#Example_3:_Python_code_for_iterating_through_all_results>
# <https://github.com/nyurik/pywikiapi/blob/master/pywikiapi/Site.py#L259>
async def query_continue(client, req_op):
    request = req_op['params']
    last_continue = {}

    while True:
        req = request.copy()
        req.update(last_continue)

        response = await client.get(req_op['url'], params=req)
        response.raise_for_status()

        result = response.json()

        if 'warnings' in result:
            print(result['warnings'])
        if 'query' in result:
            yield result['query']
        if 'continue' not in result:
            print('query-continue over, break!')
            break

        last_continue = result['continue']
