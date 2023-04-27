from dotenv import load_dotenv
import os
import arrow
import httpx
from pathlib import Path
from slugify import slugify
import aiofiles
from log_to_file import main as log
load_dotenv()


ENV = os.getenv('ENV')
URL = os.getenv('BASE_URL')
MEDIA_DIR = os.getenv('MEDIA_DIR')


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

# refs:
# <https://www.mediawiki.org/wiki/API:Continue#Example_3:_Python_code_for_iterating_through_all_results>
# <https://github.com/nyurik/pywikiapi/blob/master/pywikiapi/Site.py#L259>
async def query_continue(client, url, params):
    request = params
    last_continue = {}

    tasks = []
    while True:
        req = request.copy()
        req.update(last_continue)

        try:
            response = await client.get(url, params=req)
            result = response.json()

            if 'warnings' in result:
                print(result['warnings'])
            if 'query' in result:
                yield result['query']
            if 'continue' not in result:
                # print('query-continue over, break!')
                break

            last_continue = result['continue']

        except httpx.TimeoutException as exception:
            # print(f"query-continue e => {params['titles']}")

            sem = None
            msg = f"query-continue e => {params['titles']}\n"
            await log('error', msg, sem)
            
 

def article_exists(title) -> bool:
    WIKI_DIR = os.getenv('WIKI_DIR')
    file_path = f"{WIKI_DIR}/{slugify(title)}.html"

    return Path(file_path).is_file()


async def fetch_article(title: str, client):
    print(f"fetching article {title}...")

    params = {
        'action': 'query',
        'prop': 'revisions|images',
        'titles': title,
        'rvprop': 'content',
        'rvslots': '*',
        'list': 'backlinks',
        'bltitle': title,
        'formatversion': '2',
        'format': 'json',
        'redirects': '1'
    }

    try:
        response = await client.get(URL, params=params)
        data = response.json()

        response.raise_for_status()

        article = None
        backlinks = None
        redirect_target = None

        if 'pages' in data['query']:
            article = data['query']['pages'][0]

            # ns: -1 is part of Special Pages, we don't parse those
            if article['ns'] == -1:
                article = None

        if 'backlinks' in data['query']:
            backlinks = data['query']['backlinks']

        if 'redirects' in data['query']:
            redirect_target = data['query']['redirects'][0]['to']

        return article, backlinks, redirect_target
          

    except httpx.HTTPError as exc:
        print(f"get-article err => {exc}")
        return None, None, None


def file_exists(title: str) -> bool:
    img_path = Path(MEDIA_DIR) / title
    return Path(img_path).is_file()


async def fetch_file(title: str) -> bool:
    params = {
        'action': 'query',
        'prop': 'revisions|imageinfo',
        'iiprop': 'url|timestamp',
        'titles': title,
        'rvprop': 'timestamp',
        'rvslots': '*',
        'formatversion': '2',
        'format': 'json',
        'redirects': '1'
    }

    # we fetch all existing file revisions
    # to determine if the version we have on disk
    # has been updated meanwhile, by comparing timestamps

    file_exists = {"upstream": False, "downloaded": False}

    data = []
    context = create_context(ENV)
    timeout = httpx.Timeout(10.0, connect=60.0)

    async with httpx.AsyncClient(verify=context, timeout=timeout) as client:
        async for response in query_continue(client, URL, params):

            if 'missing' in response['pages'][0]:
                title = response['pages'][0]['title']
                msg = f"the image could not be found => {title}\n"
                sem = None

                await log('error', msg, sem)

                return False

            else:
                file_exists["upstream"] = True
                data.append(response)

    # -- read file from disk given file name
    #    and diff between timestamps
    file_last = data[0]['pages'][0]
    file_url = file_last['imageinfo'][0]['url']
    img_path = make_img_path(file_last)

    if os.path.exists(img_path):
        file_rev_ts = file_last['revisions'][0]['timestamp']
        t = check_file_revision(img_path, file_rev_ts)

        if t:
            await write_blob_to_disk(img_path, file_url)
            file_exists["downloaded"] = True

    else:
        await write_blob_to_disk(img_path, file_url)
        file_exists["downloaded"] = True
            

    # if file:
    # - has been found on upstream wiki to exist
    # - and has been downloaded (either by checking
    #   if up-to-date local copy exists, or by fetching
    #   a new copy of it)
    # we return True

    for k,v in file_exists.items():
        if v == True:
            return True

        else:
            return False


def make_img_path(file_last):

    file_url = file_last['imageinfo'][0]['url']
    file_path = file_url.split('/').pop()
    img_path = os.path.abspath(MEDIA_DIR + '/' + file_path)

    return img_path


def check_file_revision(img_path, file_revs):

    if os.path.exists(img_path):
        mtime = os.path.getmtime(img_path)
        file_ts = arrow.get(file_revs).to('local').timestamp()

        if mtime < file_ts:
            return True

    return False


async def write_blob_to_disk(file_path, file_url):
    # TODO move this on project init setup?
    media_path = os.path.abspath(MEDIA_DIR)
    if not os.path.exists(media_path):
        os.makedirs(media_path)

    req_op = {
        'verb': 'GET',
        'url': file_url,
        'params': None,
        'stream': True
    }

    context = create_context(ENV)
    async with httpx.AsyncClient(verify=context) as client:
        async with client.stream('GET', file_url) as response:
            async with aiofiles.open(file_path, mode='wb') as f:
                async for chunk in response.aiter_bytes():
                    await f.write(chunk)
