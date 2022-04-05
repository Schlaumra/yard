import json
import socket

from objects import yardlogging
from protocol.yardserver import YardServer

# TODO: Better conf
conf = json.load(open('settings/conf.json'))['server']

yardlogging.setup_server()

# Server conf
srv_hostname = conf['hostname'] if conf['hostname'] else socket.gethostbyname(socket.gethostname())
srv_port = conf['port'] if conf['port'] else 1434
srv_sock = (srv_hostname, srv_port)

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
udp_srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

server = YardServer(srv_sock, srv, udp_srv)

server.start()
