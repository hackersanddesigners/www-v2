from dotenv import load_dotenv
import os
import shutil
import requests
import json

BASE_URL = os.getenv('BASE_URL')

def fetch_article(title):
    # action=query&
    # prop=revisions&
    # titles=AntiSpoof&
    # formatversion=2&
    # redirects=1

    options = {'action': 'query',
               'prop': 'revisions|images',
               'titles': title,
               'rvprop': 'content',
               'rvslots': '*',
               'formatversion': '2',
               'format': 'json',
               'redirects': '1'}

    response = requests.get(BASE_URL, params=options)
    data = response.json()

    # print('data =>', json.dumps(data, indent=2))

    return data


def fetch_file(title):
   # print('fetch-file', title)

   options = {'action': 'query',
              'prop': 'revisions|imageinfo',
              'iiprop': 'url',
              'titles': title,
              'rvprop': 'content',
              'rvslots': '*',
              'formatversion': '2',
              'format': 'json',
              'redirects': '1'}

   response = requests.get(BASE_URL, params=options)
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

    # <https://stackoverflow.com/a/18043472>
    r = requests.get(url, stream=True)
    if r.status_code == 200:
        img_filename = url.split('/')[-1]
        img_path = dir_path + '/' + img_filename

        if not os.path.exists(img_path):
            with open(img_path, 'wb') as outf:
                r.raw.decode_content = True
                shutil.copyfileobj(r.raw, outf)
                # print('img downloaded successfully!')

            del r

        # else:
        #     print('image already exists!', img_filename)


        return img_path
