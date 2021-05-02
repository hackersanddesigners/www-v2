import socket
import json

SERVER_IP = "localhost"
SERVER_PORT = 1338

server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_sock.bind((SERVER_IP, SERVER_PORT))

print("UDP server has started and is ready to receive")

while True:
    data, addr = server_sock.recvfrom(2048)
    msg = json.loads(data)
    print('msg =>', json.dumps(msg, indent=4))
