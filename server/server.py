from socket import *

myHost = ""
myPort = 4848

sock = socket(AF_INET, SOCK_STREAM)
sock.bind((myHost, myPort))
sock.listen(5)

while True:
    connection, address = sock.accept()
    print('Server connected by', address)
    while True:
        data = connection.recv(1024)
        if not data: break
        connection.send(b'Echo=>' + data)
    connection.close()
