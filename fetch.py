from dotenv import load_dotenv
import os
import shutil
from requests import Session
from requests_helper import main as requests_helper
load_dotenv()


env = os.getenv('ENV')
url = os.getenv('BASE_URL')


def article_exists(title):

    req_op = {
        'verb': 'HEAD',
        'url': url,
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
    response = requests_helper(req, req_op, env)

    # this returns a boolean if response.status
    # is between 200-400, given the HTTP op follows
    # redirect, it should confirm us that the resource
    # actually exists?
    return response.ok


def fetch_article(title):

    req_op = {
        'verb': 'GET',
        'url': url,
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
    response = requests_helper(req, req_op, env)
    data = response.json()
    print('data =>', data)

    return data


def fetch_file(title):

    req_op = {
        'verb': 'GET',
        'url': url,
        'params': {
            'action': 'query',
            'prop': 'revisions|imageinfo',
            'iiprop': 'url',
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
    response = requests_helper(req, req_op, env)
    data = response.json()

    # print('data =>', json.dumps(data, indent=2))

    # we assume we get back an array with 1 result
    # we could map over in case of weird behaviour
    data_file = data['query']['pages'][0]
    file_url = data_file['imageinfo'][0]['url']
    file_path = write_blob_to_disk(file_url)

    # return file_path
    return {
        'caption': data_file['revisions'][0]['slots']['main']['content'],
        'url': '/' + '/'.join(file_path.split('/')[2:])
    }


def write_blob_to_disk(url):
    # print('url =>', url)

    dir_path = './wiki/assets/media'
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

    req_op = {
        'verb': 'GET',
        'url': url,
        'params': None,
        'session': False,
        'stream': True
    }

    req = Session()
    response = requests_helper(req, req_op, env)

    if response.status_code == 200:
        img_filename = url.split('/')[-1]
        img_path = dir_path + '/' + img_filename

        if not os.path.exists(img_path):
            with open(img_path, 'wb') as outf:
                response.raw.decode_content = True
                shutil.copyfileobj(response.raw, outf)
                # print('img downloaded successfully!')

            del r

        # else:
        #     print('image already exists!', img_filename)

        return img_path
