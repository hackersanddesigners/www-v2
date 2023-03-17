from dotenv import load_dotenv
import os
import arrow
import shutil
from requests import Session
from requests_helper import main as requests_helper
from requests_helper import query_continue
from pretty_json_log import main as pretty_json_log
load_dotenv()


ENV = os.getenv('ENV')
URL = os.getenv('BASE_URL')
MEDIA_DIR = os.getenv('MEDIA_DIR')
MEDIA_DIR_URI = '/'.join(os.getenv('MEDIA_DIR').split('/')[2:])

def article_exists(title) -> bool:

    req_op = {
        'verb': 'HEAD',
        'url': URL,
        'params': {
            'action': 'query',
            'prop': 'revisions|images',
            'titles': title,
            'rvprop': 'content',
            'rvslots': '*',
            'formatversion': '2',
            'format': 'json',
            'redirects': '1'
        },
        'session': False,
        'stream': True
    }

    req = Session()
    response = requests_helper(req, req_op, ENV)

    # this returns a boolean if response.status
    # is between 200-400, given the HTTP op follows
    # redirect, it should confirm us that the resource
    # actually exists?
    return response.ok


def fetch_article(title: str):
    print('fetching article...')

    req_op = {
        'verb': 'GET',
        'url': URL,
        'params': {
            'action': 'query',
            'prop': 'revisions|images',
            'titles': title,
            'rvprop': 'content',
            'rvslots': '*',
            'formatversion': '2',
            'format': 'json',
            'redirects': '1'
        },
        'session': False,
        'stream': True
    }

    req = Session()
    response = requests_helper(req, req_op, ENV)
    data = response.json()

    return data['query']['pages'][0]


def file_exists(title: str) -> bool:

    req_op = {
        'verb': 'HEAD',
        'url': URL,
        'params': {
            'action': 'query',
            'titles': title,
            'formatversion': '2',
            'format': 'json',
            'redirects': '1'
        },
        'session': False,
        'stream': False
       }

    req = Session()
    response = requests_helper(req, req_op, ENV)

    # this returns a boolean if response.status
    # is between 200-400, given the HTTP op follows
    # redirect, it should confirm us that the resource
    # actually exists?
    return response.ok


def fetch_file(title: str) -> bool:

    req_op = {
        'verb': 'GET',
        'url': URL,
        'params': {
            'action': 'query',
            'prop': 'revisions|imageinfo',
            'iiprop': 'url|timestamp',
            'titles': title,
            'rvprop': 'timestamp',
            'rvslots': '*',
            'formatversion': '2',
            'format': 'json',
            'redirects': '1'
        },
        'session': False,
        'stream': False
    }

    # we fetch all existing file revisions
    # to determine if the version we have on disk
    # has been updated meanwhile, by comparing timestamps

    data = []
    for response in query_continue(req_op, ENV):
        if 'missing' in response['pages'][0]:
            title = response['pages'][0]['title']
            print(f"the image could not be found => {title}")
            return False

        else:
            data.append(response)

    # -- read file from disk given file name
    #    and diff between timestamps
    file_last = data[0]['pages'][0]
    img_path = make_img_path(file_last)

    file_rev_ts = file_last['revisions'][0]['timestamp']

    t = check_file_revision(img_path, file_rev_ts)
    if t:
        file_url = file_last['imageinfo'][0]['url']
        write_blob_to_disk(img_path, file_url)

    # if file:
    # - has been found on upstream wiki to be existing
    # - and has been downloaded (either by checking
    #   if up-to-date local copy exists, or by fetching
    #   a new copy of it)
    # we return True (?)

    return True

    # -- return file caption and URL
    #    instead of initiating another API call

    # return {
    #     'caption': data_file['revisions'][0]['slots']['main']['content'],
    #     'url': '/' + '/'.join(file_path.split('/')[2:])
    # }


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


def write_blob_to_disk(file_path, file_url):
    # TODO move this on project init setup?
    if not os.path.exists(MEDIA_DIR):
        os.makedirs(MEDIA_DIR)

    req_op = {
        'verb': 'GET',
        'url': file_url,
        'params': None,
        'session': False,
        'stream': True
    }

    req = Session()
    response = requests_helper(req, req_op, ENV)

    if response.status_code == 200:
        with open(file_path, 'wb') as outf:
            response.raw.decode_content = True
            shutil.copyfileobj(response.raw, outf)
            print(f"File downloaded successfully! => {file_path}")

        del response
