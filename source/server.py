import json
import os
import socket
import ssl

from OpenSSL import crypto

from objects import yardlogging
from protocol.yardserver import YardServer

# TODO: Better conf
conf = json.load(open('settings/conf.json'))['server']

yardlogging.setup_server()

# Server conf
srv_hostname = conf['hostname'] if conf['hostname'] else socket.gethostbyname(socket.gethostname())
srv_port = conf['port'] if conf['port'] else 1434
srv_sock = (srv_hostname, srv_port)
ssl_conf = conf['ssl']
cert_file = ssl_conf['cert_file']
key_file = ssl_conf['key_file']

if not (os.path.isfile(cert_file) and os.path.isfile(key_file)):
    # create a key pair
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 4096)

    # create a self-signed cert
    cert = crypto.X509()
    cert.get_subject().C = ssl_conf['country_name']
    cert.get_subject().ST = ssl_conf['state_or_province_name']
    cert.get_subject().L = ssl_conf['locality_name']
    cert.get_subject().O = ssl_conf['organization_name']
    cert.get_subject().OU = ssl_conf['organization_unit_name']
    cert.get_subject().CN = srv_hostname
    cert.get_subject().emailAddress = ssl_conf['email_address']
    # cert.set_serial_number(serialNumber)
    cert.gmtime_adj_notBefore(ssl_conf['validity_start_in_seconds'])
    cert.gmtime_adj_notAfter(ssl_conf['validity_end_in_seconds'])
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, 'sha512')
    with open(cert_file, "wt") as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode("utf-8"))
    with open(key_file, "wt") as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k).decode("utf-8"))

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
udp_srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

server = YardServer(srv_sock, srv, udp_srv, cert_file, key_file)

server.start()
