import json
import logging
import socket
import uuid
from typing import Optional, Tuple

from objects.yardexceptions import SessionAlreadyExists


class ClientObj:
    """
    An object-class for saving information about a client.

    id_len: int = The required length of the client_id

    pending_packages =  [
        (ses, package),
        (ses, package),
        ...
    ]

    :param client_id: str: The id of the client. (e.g. ABCD1234)
    :param fingerprint: uuid.UUID: The unique id for the client -> UUIDv4
    :param online: bool(Optional): If the client is online or not
    :param sock: socket.socket(Optional): If the client is connected then sock is the current socket
    :raises ValueError: If you pass the wrong format of the client_id or fingerprint an error will be raised.
    """
    conf = json.load(open('settings/conf.json'))['server']
    id_len: int = conf['id_len']

    client_id: str = None
    fingerprint: uuid.UUID = None
    sessions: dict[int: 'SessionObj'] = None
    online: bool = None
    socket: Optional['socket.socket'] = None
    pending_packages: list[Tuple[int, list]] = None

    def __init__(self, client_id: str, fingerprint: uuid.UUID, online: bool = False, sock=None):
        if len(client_id) == self.id_len:
            if fingerprint.version == 4:
                self.client_id = client_id
                self.fingerprint = fingerprint
                self.sessions = {}
                self.online = online
                self.socket = sock
                self.pending_packages = []
            else:
                raise ValueError('Client fingerprint is not version 4')
        else:
            raise ValueError(f'Client ID is not exactly {self.id_len} long: {len(client_id)} chars')

    def __str__(self):
        return str({'client_id': str(self.client_id),
                    'fingerprint': str(self.fingerprint),
                    'sessions': str(self.sessions),
                    'pending_packages': str(self.pending_packages),
                    'online': str(self.online)})

    def add_session(self, session: 'SessionObj'):
        """
        Add a session to clients sessions.

        :param session: session.Session: The session that you want to add
        :raises SessionAlreadyExists: If session already exists
        """

        if not self.sessions.get(session.session_id, None):
            self.sessions[session.session_id] = session
        else:
            raise SessionAlreadyExists(f"Client has already a session with this ID: {session.session_id}")

    def pop_session(self, ses: int) -> Tuple['SessionObj', Optional['SessionObj']]:
        """
        Pop the session of the passed id.

        :param ses: int: The id of the session
        :return: (SessionObj, SessionObj)
        """

        partner = self.get_partner_of_session(ses)
        if partner:
            logging.getLogger('yard_server.client').debug(
                f"Delete session {ses} of {self.client_id} and {partner.client_id}")
            return self.sessions.pop(ses), partner.sessions.pop(ses)
        else:
            logging.getLogger('yard_server.client').debug(
                f"Delete session {ses} of {self.client_id}")
            return self.sessions.pop(ses), None

    def set_online(self, sock: 'socket.socket') -> None:
        """
        Set the client online.

        First it ensures that the client is offline. Then he sets the client online and assigns the new socket.

        :param sock: socket.socket: The new socket of the client
        :return: None
        """

        self.set_offline(leave_sock=True)
        self.online = True
        self.socket = sock
        logging.getLogger('yard_server.client').info(f"{self.fingerprint} is now online")

    def set_offline(self, *, leave_sock: bool = False) -> None:
        """
        Set the client offline

        1. Closes socket.
        2. Set to offline
        3. Delete all sessions
        4. Delete pending packages

        :param leave_sock: bool: Delete sock or not
        :return: None
        """
        if not leave_sock:
            self.socket.close()
            self.socket = None
        self.online = False
        self.delete_all_sessions()
        self.sessions = {}
        self.pending_packages = []
        logging.getLogger('yard_server.client').info(f"{self.fingerprint} is now offline")

    def is_initialized(self, sock: 'socket.socket'):
        """
        Check if the client is initialized and has this exact socket
        :param sock: The socket that the client must have
        :return:
        """
        return self.socket == sock and self.online and self.fingerprint and self.client_id

    ######################
    #     Sessions       #
    ######################

    def get_partner_of_session(self, session_id: int) -> Optional['ClientObj']:
        """
        Get the partner client of the passed session id.

        :param session_id: int: The id of the session
        :return: client object of partner | None
        """

        session = self.sessions.get(session_id, None)
        if session:
            return session.get_partner(self.client_id)
        return None

    def session_exists(self, target: 'ClientObj') -> int:
        """
        Checks if a session already exists with passed target.

        :param target: ClientObj: The target
        :return: int: The session or 0
        """
        for session in self.sessions.values():
            if session.connection[0] == target or session.connection[1] == target:
                return session.session_id
        else:
            return 0

    def delete_pending_packages_per_session(self, ses: int) -> None:
        """
        Delete pending packages for given session.

        :param ses: int: ID of the session
        :return: None
        """
        for index, package in enumerate(self.pending_packages or []):
            if package[0] == ses:
                logging.getLogger('yard_server.client').debug(
                    f"Delete pending packages {self.pending_packages.pop(index)}")

    def delete_session(self, ses: int) -> bool:
        """
        Delete session with given session_id.

        :param ses: int: ID of the session
        :return: True -> succeeded | False -> failed
        """

        logging.getLogger('yard_server.client').debug(f"Terminate session: {ses}")

        # First clear the already pending packages for the given session
        self.delete_pending_packages_per_session(ses)

        # If session exists, pop session, get partner and do the same -> return True
        if self.sessions.get(ses, None):
            target_client = self.get_partner_of_session(ses)
            self.pop_session(ses)
            if target_client:
                target_client.delete_pending_packages_per_session(ses)
            return True

    def delete_all_sessions(self) -> None:
        """
        Delete all sessions and pending packages.

        :return: None
        """
        for key in tuple(self.sessions.keys()):
            self.delete_session(key)
