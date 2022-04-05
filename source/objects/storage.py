import logging
import socket
import uuid
from typing import Optional, Dict, Tuple, List

from objects import secret
from objects.clientobj import ClientObj
from objects.sessionobj import SessionObj
from objects.connectionobj import ConnectionObj
from protocol.yardtransmission import YardTransmission


class ClientStorage:
    """
    ClientStorage to save clients while operation.

    clients: Dict[str: ClientObj] -> The saved clients in dict format.
    """
    max_session_per_client = 256
    clients: Dict['str', 'ClientObj'] = None

    def __init__(self):
        self.clients = {}

    def get_client(self, client_id: str) -> Optional[ClientObj]:
        """
        Get Client by id or None.

        :param client_id: str: The id of the client
        :return: ClientObj | None
        """

        return self.clients.get(client_id, None)

    def get_client_by_fingerprint(self, fingerprint: uuid.UUID) -> Optional[ClientObj]:
        """
        Get client by fingerprint or return None.

        :param fingerprint: uuid.UUID: The fingerprint of the client
        :return: ClientObj | None
        """

        for client_id, client in self.clients.items():
            if client.fingerprint == fingerprint:
                return client

    def get_client_by_socket(self, sock: socket.socket) -> Optional[ClientObj]:
        """
        Get client by socket or return None.

        :param sock: socket.socket: The socket of the client
        :return: ClientObj | None
        """

        for client_id, client in self.clients.items():
            if client.socket == sock:
                return client

    def add_client(self, client_id: str, fingerprint: uuid.UUID, online: bool, sock: socket.socket) -> ClientObj:
        """
        Add client to clients.

        :param client_id: str
        :param fingerprint: uuid.UUID
        :param online: bool: True -> online; False -> offline
        :param sock: socket.socket
        :return: ClientObj: The added client
        :raises ValueError: If you pass the wrong format of the client_id or fingerprint an error will be raised.
        """
        logging.getLogger('yard_server.client').debug(
            f"Adding client: ID: {client_id}, Fingerprint: {fingerprint}, Online: {online}")
        self.clients[client_id] = ClientObj(client_id, fingerprint, online, sock)
        return self.clients[client_id]

    def create_client(self,
                      fingerprint: uuid.UUID,
                      *,
                      sock: socket.socket = None) -> ClientObj:
        """
        Create a client with given fingerprint and add it to the list.

        :param fingerprint: uuid.UUID: The fingerprint of the client.
        :param sock: socket.socket(Optional): The socket to whom the client is connected
        :return: ClientObj: The created client
        :raises ValueError: If you pass the wrong format of the fingerprint an error will be raised.
        """

        clt = self.get_client_by_fingerprint(fingerprint)
        if not clt:
            # As long as the id is not unique
            while True:
                client_id = secret.create_secret(ClientObj.id_len, numbers=True, alphabet=(False, True))
                if not self.get_client(client_id):
                    # ID is unique
                    clt = self.add_client(client_id, fingerprint, True, sock)
                    logging.getLogger('yard_server.client').info(f"Created client: {clt}")
                    return clt
        else:
            # Client already exists
            logging.getLogger('yard_server.client').debug(f"Client already exists: {fingerprint}, {clt.client_id}")
            clt.set_online(sock)
            return clt

    def update_client(self,
                      client_id: str,
                      *,
                      fingerprint: uuid.UUID = None,
                      sessions: dict[int: SessionObj] = None,
                      pending_packages: list[Tuple[int, list]] = None,
                      online: bool = None,
                      sock: socket.socket = None) -> ClientObj:
        """
        Update the client with the given client_id.

        :param client_id: str: The ID of the client
        :param fingerprint: uuid.UUID: The fingerprint of the client
        :param sessions: dict[session_id: SessionObj]: The desired sessions
        :param pending_packages: list[Tuple[session_id, package]]: The desired pending_packages
        :param online: bool: True -> online; False -> offline
        :param sock: socket.socket: The socket of the client
        :return: ClientObj: The update client
        """

        client = self.get_client(client_id)
        if fingerprint:
            client.fingerprint = fingerprint
        if sessions:
            client.sessions = sessions
        if pending_packages:
            client.pending_packages = pending_packages
        if online is not None:
            client.online = online
        if sock:
            client.socket = sock
        return client

    def pop_client(self, client_id: str) -> ClientObj:
        """
        Pop client with given id.

        :param client_id: str: ID of the client
        :return: ClientObj
        """

        return self.clients.pop(client_id)

    def create_session(self, client1: 'ClientObj', client2: 'ClientObj') -> int:
        """
        Create a session and return id.

        It will be ensured that the session number is not used by client and partner.

        :param client1: ClientObj: The client
        :param client2: ClientObj: The partner
        :return: int: The ID of the created session
        :raises OverflowError: No session left for client. MAX is 255 (sum of client and target).
        """
        storage_logger = logging.getLogger('yard_server.storage')
        exist1 = client1.session_exists(client2)
        exist2 = client2.session_exists(client1)
        session_exist = exist1 if exist1 == exist2 else None

        """print("Lhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhh")
        print("client2", exist1)
        print("client2", exist2)
        print("session_exist", session_exist)
        print(client1.sessions)"""
        if session_exist:
            storage_logger.warning(f"Session already exists for: {client1.fingerprint}, {client2.fingerprint}")
            return session_exist

        for i in range(1, self.max_session_per_client):
            if not client1.sessions.get(i, None):
                if not client2.sessions.get(i, None):
                    session = SessionObj(i, (client1, client2))
                    client1.add_session(session)
                    client2.add_session(session)
                    return i
        else:
            storage_logger.error(f"No session id left for: {client1.fingerprint}, {client2.fingerprint}")
            raise OverflowError("Too many sessions for client or partner")


class ConnectionStorage:
    connections: List['ConnectionObj'] = None

    def __init__(self):
        self.connections = []

    def __str__(self):
        string = "["
        for conn in self.connections:
            string += str(conn) + " "
        return string[:-1] + "]"

    def add_connection(self,
                       client_id: str,
                       ses: int, online: bool,
                       *,
                       fingerprint: Optional['uuid.UUID'] = None,
                       transmission: Optional['YardTransmission'] = None):
        conn_id = None
        conn_fp = None

        if fingerprint:
            conn_fp = self.get_connection_by_fingerprint(fingerprint)
        if client_id:
            conn_id = self.get_connection_by_id(client_id)

        if conn_id:
            if not fingerprint or not conn_id.fingerprint or conn_id.fingerprint == fingerprint:
                # Update based on id
                # Or Update connection based on same id and fp
                conn = conn_id
            else:
                # TODO: Throw exception
                raise Exception
                # Client exists with same id but fingerprint is different
        elif conn_fp:
            conn = conn_fp
            # Update based on fp, update client_id
        else:
            # Not already existing -> add
            self.connections.append(ConnectionObj(client_id, ses, fingerprint, online, transmission))
            return len(self.connections) - 1

        if conn:
            conn.client_id = client_id
            conn.fingerprint = fingerprint
            conn.session_id = ses
            conn.online = online
            conn.transmission = transmission
            return self.connections.index(conn)

    def get_connection_by_id(self, client_id: str):
        x = [x for x in self.connections if x.client_id == client_id]
        return x[0] if x else None

    def get_connection_by_fingerprint(self, fingerprint: uuid.UUID):
        x = [x for x in self.connections if x.fingerprint == fingerprint]
        return x[0] if x else None

    def get_connection_by_ses(self, ses: int):
        x = [x for x in self.connections if x.session_id == ses]
        return x[0] if x else None

    def get_connection_by_transmission(self, transmission: YardTransmission):
        x = [x for x in self.connections if x.transmission == transmission]
        return x[0] if x else None
