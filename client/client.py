import sys
from socket import *
serverHost = 'localhost'
serverPort = 4848

message = [b'Hello network world']

if len(sys.argv) > 1:
    serverHost = sys.argv[1]
    if len(sys.argv) > 2:
        message = (x.encode() for x in sys.argv[2:])

sock = socket(AF_INET, SOCK_STREAM)
sock.connect((serverHost, serverPort))

for line in message:
    sock.send(line)
    data = sock.recv(1024)
    print('Client received:', data)

sock.close()
