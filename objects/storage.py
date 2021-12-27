import socket
from typing import Optional

from objects import logging, secret
import uuid


class Session:
    session_id = None
    connection = None

    def __init__(self, session_id: int, connection: tuple):
        self.session_id = session_id
        self.connection = connection

    def get_partner(self, own_id):
        for client in self.connection:
            if client.client_id != own_id:
                return client

    def __str__(self):
        return str({'session_id': self.session_id, 'connection': self.connection})


class Client:
    client_id = None
    fingerprint = None
    sessions = None
    online = False
    socket = None

    def __init__(self, client_id: str, fingerprint: uuid.UUID, online: bool = False, sock=None):
        self.client_id = client_id
        self.fingerprint = fingerprint
        self.sessions = {}
        self.online = online
        self.socket = sock

    def __str__(self):
        return str({'client_id': self.client_id,
                    'fingerprint': self.fingerprint,
                    'sessions': self.sessions,
                    'online': self.online})

    def add_session(self, session: Session) -> bool:
        if not self.sessions.get(session.session_id, None):
            self.sessions[session.session_id] = session
            return True
        return False

    def get_partner_of_session(self, session_id: int):
        session = self.sessions.get(session_id, None)
        if session:
            return session.get_partner(self.client_id)
        return None

    def delete_session(self, ses):
        partner = self.get_partner_of_session(ses)
        logging.log(f"Delete session {ses} of {self.client_id} and {partner.client_id}", target="CLIENT", level=1)
        partner.sessions.pop(ses)
        self.sessions.pop(ses)

    def get_dict(self):
        return {'client_id': self.client_id,
                'fingerprint': self.fingerprint,
                'sessions': self.sessions,
                'online': self.online,
                'socket': self.socket}

    def set_online(self, online: bool):
        logging.log(f"{self.fingerprint} is now {'online' if online else 'offline'}", target="CLIENT", level=1)
        self.online = online


class ClientStorage:
    id_len = 8
    clients = {}

    # {
    #   'id': {
    #       'fingerprint': {}
    #       'sessions': {}
    #       'online': BOOL
    #       'socket': socket.socket
    #   }
    # }

    # clients['id']['sessions']['session-id'] = {
    #   'partner': id
    #   'status': BOOL
    # }
    #

    def get_client(self, client_id) -> Optional[Client]:
        return self.clients.get(client_id, None)

    def client_exists(self, client_id):
        if self.clients.get(client_id, None):
            return client_id
        else:
            return None

    def get_client_id_by_fingerprint(self, fingerprint: uuid.UUID) -> Optional[str]:
        for client_id, client in self.clients.items():
            if client.fingerprint == fingerprint:
                return client_id
        return None

    def get_client_by_fingerprint(self, fingerprint) -> Optional[Client]:
        for client_id, client in self.clients.items():
            if client.fingerprint == fingerprint:
                return client
        return None

    def get_client_id_by_socket(self, sock) -> Optional[str]:
        for client_id, client in self.clients.items():
            if client.socket == sock:
                return client_id
        return None

    def get_client_by_socket(self, sock) -> Optional[Client]:
        for client_id, client in self.clients.items():
            if client.socket == sock:
                return client
        return None

    def add_client(self, client_id: str, fingerprint: uuid.UUID, sessions: list, online: bool, sock: socket.socket):
        logging.log(
            f"Adding client: ID: {client_id}, Fingerprint: {fingerprint}, Sessions: {sessions}, Online: {online}",
            target="CLIENT",
            level=1)
        self.clients.update({client_id: Client(client_id, fingerprint, online, sock)})

    def create_client(self,
                      fingerprint: uuid.UUID,
                      *args,
                      sessions: list = None,
                      online: bool = True,
                      sock: socket.socket = None) -> str:

        client = self.get_client_by_fingerprint(fingerprint)
        if not client:
            while True:
                client_id = secret.create_secret(self.id_len, numbers=True, alphabet=(False, True))
                if not self.get_client(client_id):
                    sessions = sessions if sessions else {}  # ATTENTION: Override sessions
                    self.add_client(client_id, fingerprint, sessions, online, sock)
                    logging.log(f"Created client: {self.clients[client_id]}", target="CLIENT", level=1)
                    return client_id
        else:
            logging.log(f"Client already exists: {fingerprint}, {client.client_id}", target="CLIENT", level=3)
            client.set_online(online)
            client.socket = sock
            client.sessions = {}  # ATTENTION: Deletes all sessions
            return client.client_id

    def pop_client(self, client_id: str):
        return self.clients.pop(client_id)

    def set_client_status(self, client_id, online):
        logging.log(f"Client {client_id} is set to {'online' if online else 'offline'}", target="CLIENT", level=0)
        self.update_client(client_id, online=online)

    def update_client(self,
                      client_id: str,
                      *args,
                      fingerprint: uuid.UUID = None,
                      sessions: dict = None,
                      online: bool = None,
                      sock: socket.socket = None):

        client = self.get_client(client_id)
        if fingerprint:
            client.fingerprint = fingerprint
        if sessions:
            client.sessions = sessions
        if online is not None:
            client.online = online
        if sock:
            client.socket = sock

    def add_session(self,
                    session_id: int,
                    client1_id: str,
                    client2_id: str,
                    *args,
                    status: bool):

        client1 = self.get_client(client1_id)
        client2 = self.get_client(client2_id)
        session = Session(session_id, (client1, client2))
        client1.add_session(session)
        client2.add_session(session)

    def create_session(self, client1_id: str, client2_id: str) -> int:
        client1 = self.get_client(client1_id)
        client2 = self.get_client(client2_id)
        for i in range(1, 255):
            if not client1.sessions.get(i, None):
                if not client2.sessions.get(i, None):
                    self.add_session(i, client1_id, client2_id, status=True)
                    return i
        else:
            # TODO Create exception
            logging.log(f"No session id left for: {client1.fingerprint}, {client2.fingerprint}",
                        target="SESSION",
                        level=3)
            raise Exception

    def get_sessions(self, client1_id):
        client1 = self.get_client(client1_id)
        if client1:
            return client1.sessions
