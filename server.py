from dotenv import load_dotenv
import os
import traceback
import socket
import json
from jinja2 import Environment, FileSystemLoader
from fetch import fetch_article
from parser import parser
from write_to_disk import main as write_to_disk
load_dotenv()


def main(SERVER_IP: str, SERVER_PORT: int):
    env = Environment(loader=FileSystemLoader('templates'), autoescape=True)

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_sock.bind((SERVER_IP, SERVER_PORT))

    print("UDP server has started and is ready to receive...",
          [SERVER_IP, SERVER_PORT])

    while True:
        data, addr = server_sock.recvfrom(2048)
        msg = json.loads(data)
        print('msg =>', json.dumps(msg, indent=4))

        # -- we have the UPD message, let's fetch the full article now
        try:
            data = fetch_article(msg['title'])
            article = parser(data)

            t = env.get_template('article.html')
            document = t.render(article=article)

            write_to_disk(article, document)

        except Exception as e:
            traceback.print_exc()


if __name__ == '__main__':

    SERVER_IP = os.getenv('SERVER_IP')
    SERVER_PORT = int(os.getenv('SERVER_PORT'))

    main(SERVER_IP, SERVER_PORT)
