import requests
import json

# base_url = 'https://wiki.hackersanddesigners.nl/api.php?'
BASE_URL = 'http://hd-mw.test/api.php?' # change this to .env

def fetch(title):
    # action=query&
    # prop=revisions&
    # titles=AntiSpoof&
    # formatversion=2&
    # redirects=1
    
    options = {'action': 'query',
               'prop': 'revisions|pageimages',
               'titles': title,
               'rvprop': 'content',
               'rvslots': '*',
               'formatversion': '2',
               'format': 'json',
               'redirects': '1'}
    
    response = requests.get(BASE_URL, params=options)
    data = response.json()

    print('data =>', json.dumps(data, indent=4))

    return data
