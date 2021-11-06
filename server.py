import traceback
import sys
import socket
import json
import wikitextparser as wtp
from jinja2 import Environment, FileSystemLoader
from fetch import fetch
from parser import parser

env = Environment(loader=FileSystemLoader('templates'), autoescape=True)

SERVER_IP = "localhost"
SERVER_PORT = 1338

server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_sock.bind((SERVER_IP, SERVER_PORT))

print("UDP server has started and is ready to receive")

while True:
    data, addr = server_sock.recvfrom(2048)
    msg = json.loads(data)
    print('msg =>', json.dumps(msg, indent=4))

    #-- we have the UPD message, let's fetch the full article now
    try: 
        data = fetch(msg['title']) 
        article = parser(data)
        
        t = env.get_template('article.html')
        document = t.render(article=article)

        with open('./wiki/%s.html' % article['slug'], 'w') as f:
            try:
                f.write(document)
                print('✓ %s-article "%s" has been correctly written to disk' % (article['slug'], article['title']))
            except Exception as e:
                print('✕ error for %s-article "%s" =>' % (article['slug'], article['title']), e)

    except Exception as e:
        traceback.print_exc()
