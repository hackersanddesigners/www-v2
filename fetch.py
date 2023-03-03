from dotenv import load_dotenv
import os
import time
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

def article_exists(title):

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


def fetch_article(title):

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

    return data


def file_exists(title):

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
        'stream': True
    }

    req = Session()
    response = requests_helper(req, req_op, ENV, False)

    # this returns a boolean if response.status
    # is between 200-400, given the HTTP op follows
    # redirect, it should confirm us that the resource
    # actually exists?
    print('fetch-file-exists =>', response.ok)
    return response.ok


def fetch_file(title):

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
    # has been updated meanwhile, by comparing timestamps?

    data = []
    for response in query_continue(req_op, ENV):
        if 'missing' in response['pages'][0]:
            title = response['pages'][0]['title']
            print(f"the image could not be found => {title}")
            return None

        else:
            print('response =>', response)
            data.append(response)

    # -- read file from disk given file name
    #    and diff between timestamps
    file_last = data[0]['pages'][0]
    file_revisions = file_last['revisions']

    file_url = file_last['imageinfo'][0]['url']
    file_path = file_url.split('/').pop()
    img_path = os.path.abspath(MEDIA_DIR + '/' + file_path)

    if os.path.exists(img_path):
        print(f"img path exists => {img_path}")

        mtime = os.path.getmtime(img_path)
        file_ts = arrow.get(file_revisions[0]['timestamp']).to('local').timestamp()

        if mtime < file_ts:
            print('upstream file is newer than local copy. fetch copy!')
            file_url = file_last['imageinfo'][0]['url']
            write_blob_to_disk(file_path, file_url)

        else:
            print('upstream file has not been changed after local copy was made')

    else:
        print(f"img path not yet there => {img_path}")
        file_url = file_last['imageinfo'][0]['url']
        write_blob_to_disk(file_path, file_url)

    # # return file_path
    # return {
    #     'caption': data_file['revisions'][0]['slots']['main']['content'],
    #     'url': '/' + '/'.join(file_path.split('/')[2:])
    # }


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

        return file_path
