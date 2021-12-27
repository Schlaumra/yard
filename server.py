import socket
import threading
import json
import uuid

from protocol import protocol
from objects import storage, logging


class YardServer:
    control_socket = None
    control_server = None
    control_channel = None

    transmission_socket = None
    transmission_server = None
    transmission_channel = None

    client_storage = None

    connections = []

    pending_packages = {}
    """
    pending_packages = {
        sock: [(ses, package), (ses, package), ...],
        sock: ...
        ...
    }
    
    package = [header, payload]
    """
    # TODO Create fingerprint check (fingerprint and socket are connected MITM) Send fingerprint encrypted

    def __init__(self, control_socket, control_server, transmission_socket=None, transmission_server=None):
        logging.log("Initializing Control server", target="INIT", level=0)
        self.control_socket = control_socket
        self.control_server = control_server
        self.control_channel = protocol.YardControlChannel()
        self.control_server.bind(self.control_socket)

        logging.log("Initializing Transmission server", target="INIT", level=0)
        self.transmission_socket = transmission_socket
        self.transmission_server = transmission_server
        # self.transmission_channel = protocol.YardControlChannel()
        # self.transmission_server.bind(self.control_socket)

        self.client_storage = storage.ClientStorage()

    def delete_pending_packages_per_session(self, sock, ses):
        for index, package in enumerate(self.pending_packages.get(sock, [])):
            if package[0] == ses:
                logging.log(f"Delete pending packages {self.pending_packages[sock].pop(index)}",
                            target="TERMINATE",
                            level=0)

    def sock_is_initialized(self, sock):
        cl = self.client_storage.get_client_by_socket(sock)
        return cl and cl.socket == sock and cl.online and cl.fingerprint and cl.client_id

    def terminate_session(self, sock, ses) -> bool:
        logging.log(f"Terminate session: {ses}",
                    target="TERMINATE",
                    level=0)
        self.delete_pending_packages_per_session(sock, ses)
        cl = self.client_storage.get_client_by_socket(sock)
        if cl.sessions.get(ses, None):
            target_client = cl.get_partner_of_session(ses)
            if target_client:
                if target_client.socket:
                    self.delete_pending_packages_per_session(target_client.socket, ses)
            cl.delete_session(ses)
            return True
        else:
            return False

    def answer_message(self, sock, package, *args, ses=0, **kwargs) -> bool:
        try:
            header, payload = package
            typ = header['typ']
            ses = header['ses']
            logging.log(f"Answer to message type: {self.control_channel.types[typ]}", target="CONNECTION", level=0)

            if typ == self.control_channel.INIT:
                client_id = self.client_storage.create_client(uuid.UUID(payload), sock=sock)
                cl = self.client_storage.get_client(client_id)
                for key in tuple(cl.sessions.keys()):
                    self.terminate_session(sock, key)
                self.pending_packages[sock] = []
                self.control_channel.send(sock, ses, self.control_channel.ANS, client_id)
            elif self.sock_is_initialized(sock):
                if typ == self.control_channel.CLOSE:
                    return False
                elif typ == self.control_channel.PING:
                    if len(self.pending_packages[sock]) > 0:
                        package = self.pending_packages[sock].pop(0)[1]
                        ses = package[0]['ses']
                        data = package[1]
                    else:
                        data = ""
                    self.control_channel.send(sock, ses, self.control_channel.ANS, str(data))
                elif typ == self.control_channel.REQ:
                    client1_id = self.client_storage.get_client_id_by_socket(sock)
                    client2_id = self.client_storage.client_exists(payload)
                    if client2_id:
                        session_id = self.client_storage.create_session(client1_id, client2_id)
                        logging.log(f"Create Session {session_id} ({client1_id}, {client2_id})",
                                    target="SESSION",
                                    level=1)
                        self.control_channel.send(sock, ses, self.control_channel.ANS, str(session_id))
                    else:
                        self.control_channel.send(sock, ses, self.control_channel.ANS, str(0))
                elif typ == self.control_channel.CONN:
                    client = self.client_storage.get_client_by_socket(sock)
                    target_client = client.get_partner_of_session(ses)
                    if target_client:
                        if target_client.socket:
                            package = (self.control_channel.create_header(ses, self.control_channel.ANS, pl=payload),
                                       payload)
                            self.pending_packages[target_client.socket].append((ses, package))
                            self.control_channel.send(sock, ses, self.control_channel.ANS, "")
                    else:
                        self.control_channel.send(sock, 0, self.control_channel.WARN, "Session doesn't exists")
                elif typ == self.control_channel.TERM:
                    if self.terminate_session(sock, ses):
                        self.control_channel.send(sock, 0, self.control_channel.ANS, "")
                    else:
                        try:
                            self.control_channel.send(sock, 0, self.control_channel.ERR, "Session doesn't exists")
                        finally:
                            return False
                elif typ == self.control_channel.REN:
                    old_id = self.client_storage.get_client_id_by_fingerprint(uuid.UUID(payload))
                    for key in tuple(self.client_storage.get_client(old_id).sessions.keys()):
                        self.terminate_session(sock, key)
                    old = self.client_storage.pop_client(old_id)
                    new_id = self.client_storage.create_client(fingerprint=old.fingerprint,
                                                               online=True,
                                                               sock=sock)
                    logging.log(f"Renewed ID for {old.fingerprint} ({old_id} to {new_id})", target="CONNECTION", level=1)
                    self.control_channel.send(sock, ses, self.control_channel.ANS, new_id)
                else:
                    try:
                        self.control_channel.send(sock, ses, self.control_channel.ERR, "Unknown message type")
                    finally:
                        return False
            else:
                try:
                    self.control_channel.send(sock, ses, self.control_channel.ERR, "Client is not initialized")
                finally:
                    logging.log("Client is not initialized")
                    return False
            return True
        except Exception as e:
            try:
                self.control_channel.send(sock, ses, self.control_channel.ERR, "")
            finally:
                print(e)
                return False

    def handle_client(self, connection, address):
        self.connections.append(connection)
        try:
            logging.log("Accepting {}:{}".format(*address), target="CONNECTION", level=1)
            while True:
                package = self.control_channel.receive_data(connection)
                logging.log("Received data from {}:{} || Header: {} || Payload: {}".format(*address, *package),
                            target="CONNECTION",
                            level=1)
                logging.log("Answer to {}:{}".format(*address),
                            target="CONNECTION",
                            level=1)
                if not self.answer_message(connection, package):
                    break
        except Exception as n:
            print("exception:", n.__str__)
        finally:
            try:
                self.control_channel.send(connection, 0, self.control_channel.CLOSE, "")
            except:
                pass
            finally:
                logging.log("Closing connection {}:{}".format(*address), target="CONNECTION", level=1)
                cl = self.client_storage.get_client_by_socket(connection)
                if cl:
                    for key in tuple(cl.sessions.keys()):
                        self.terminate_session(connection, key)
                    cl.set_online(False)
                    cl.socket.close()
                    cl.socket = None
                self.pending_packages.pop(connection, None)

    def server_loop(self):
        try:
            while True:
                logging.log("Control server is waiting for connections", target="MAIN", level=1)
                connection, address = self.control_server.accept()
                thread = threading.Thread(target=self.handle_client, args=(connection, address))
                logging.log("Control server starts new thread", target="MAIN", level=0)
                thread.start()
        except:
            self.stop()

    def start(self):
        logging.log("Control server is starting", target="STARTING", level=1)
        logging.log("Control server is now listening", target="STARTING", level=1)
        self.control_server.listen()
        thread = threading.Thread(target=self.server_loop)
        logging.log("Control server starts new thread", target="STARTING", level=0)
        thread.start()

    def stop(self):
        logging.log("Control server is now stopping", target="STOPPING", level=1)
        logging.log("Closing connections", target="STOPPING", level=0)
        for i in self.connections:
            i.close()
        self.control_server.close()
        self.transmission_server.close()


conf = json.load(open('settings/conf.json'))['server']

# Server conf
srv_hostname = conf['hostname'] if conf['hostname'] else socket.gethostbyname(socket.gethostname())
srv_port = conf['port'] if conf['port'] else 1434
srv_sock = (srv_hostname, srv_port)

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

server = YardServer(srv_sock, srv)

try:
    server.start()
except:
    server.stop()
