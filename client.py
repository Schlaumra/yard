import socket
import json
import time
import uuid

from protocol import protocol
from objects import logging


class YardClient:
    control_socket = None
    control_client = None
    control_channel = None

    transmission_socket = None
    transmission_client = None
    transmission_channel = None

    fingerprint = uuid.uuid4()

    def __init__(self, control_socket, control_client, transmission_socket=None, transmission_client=None):
        print(control_socket)
        logging.log("Initializing Control client", target="INIT", level=0)
        self.control_socket = control_socket
        self.control_client = control_client
        self.control_channel = protocol.YardControlChannel()

        logging.log("Initializing Transmission client", target="INIT", level=0)
        self.transmission_socket = transmission_socket
        self.transmission_client = transmission_client
        # self.transmission_channel = protocol.YardControlChannel()
        # self.transmission_server.bind(self.control_socket)

    def connect(self):
        logging.log("Connecting to {}:{}".format(*self.control_socket), target="CONNECTING", level=1)
        self.control_client.connect(self.control_socket)

    def send_message(self, typ, *args, ses=0, data="", **kwargs):
        if typ == self.control_channel.INIT:
            logging.log(f"Sending INIT message to {self.control_socket}", target="Sending", level=0)
            # TODO: Save fingerprint
            self.control_channel.send(self.control_client, ses, typ, str(self.fingerprint))
        elif typ == self.control_channel.CLOSE:
            logging.log(f"Sending CLOSE message to {self.control_socket}", target="Sending", level=0)
            self.control_channel.send(self.control_client, ses, typ, "CLOSE connection")
        elif typ == self.control_channel.PING:
            logging.log(f"Sending PING message to {self.control_socket}", target="Sending", level=0)
            self.control_channel.send(self.control_client, ses, typ, "PING")
        elif typ == self.control_channel.REQ:
            logging.log(f"Sending REQ message to {self.control_socket}", target="Sending", level=0)
            id1 = input('Gib die ID ein: ')
            self.control_channel.send(self.control_client, ses, typ, id1)
        elif typ == self.control_channel.CONN:
            logging.log(f"Sending CONN message to {self.control_socket}", target="Sending", level=0)
            ses = int(input("session: "))
            payload = input("payload: ")
            self.control_channel.send(self.control_client, ses, typ, payload)
        elif typ == self.control_channel.TERM:
            logging.log(f"Sending TERM message to {self.control_socket}", target="Sending", level=0)
            ses = int(input("session: "))
            self.control_channel.send(self.control_client, ses, typ, "TERMINATE session")
        elif typ == self.control_channel.REN:
            logging.log(f"Sending REN message to {self.control_socket}", target="Sending", level=0)
            self.control_channel.send(self.control_client, ses, typ, str(self.fingerprint))
        elif typ == self.control_channel.ANS:
            logging.log(f"Sending ANS message to {self.control_socket}", target="Sending", level=0)
            self.control_channel.send(self.control_client, ses, typ, data)
        elif typ == self.control_channel.ERR:
            logging.log(f"Sending ERR message to {self.control_socket}", target="Sending", level=0)
            self.control_channel.send(self.control_client, ses, typ, data)

    def receive(self) -> list:
        pkg = self.control_channel.receive_data(self.control_client)
        logging.log("Received data from {}:{} | Header: {} || Payload: {}".format(*self.control_socket, *pkg), target="CONNECTION", level=0)
        return pkg

    def send_receive(self, typ, *args, ses=0, data="") -> list:
        self.send_message(typ, ses=ses, data=data)
        return self.receive()

    def close(self):
        self.control_client.close()


conf = json.load(open('settings/conf.json'))

clt_socket = (conf['server']['hostname'], conf['server']['port'])
logging.log("Starting client ...", target="STARTING", level=1)
clt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client = YardClient(clt_socket, clt)
client.connect()

try:
    while True:
        x = int(input("Send message: "))
        if x == protocol.YardControlChannel.CLOSE:
            client.send_message(protocol.YardControlChannel.CLOSE)
            break
        pkg = client.send_receive(x)
        if pkg[0]['typ'] == protocol.YardControlChannel.ERR:
            logging.log(pkg[1], target="CLIENT", level=4)
            input()
            break
        elif pkg[0]['typ'] == protocol.YardControlChannel.WARN:
            logging.log(pkg[1], target="CLIENT", level=3)
        elif pkg[0]['typ'] == protocol.YardControlChannel.CLOSE:
            break
except Exception as e:
    print("Exeption", e)
    input()
finally:
    client.close()
