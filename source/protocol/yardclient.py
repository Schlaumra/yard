import json
import os
import secrets
import socket
import time
import uuid
import logging
from typing import Union, Tuple, Any

from protocol import protocol

# TODO: On exit close everything
# TODO: Ping set to default
from protocol.yardtransmission import YardTransmission


class YardClient:
    # TODO: PROBLEM if receive it receives of other request

    control_socket = None
    control_client = None
    control_channel = None

    settings = None
    defaultSettings = {"fingerprint": str(uuid.uuid4())}

    is_connected = False

    # {"fingerprint": uuid}

    def __init__(self, control_socket: Any, control_client: socket.socket):
        init_logger = logging.getLogger('yard_client.protocol.init')
        init_logger.debug("Initializing Control client")
        self.control_socket = control_socket
        self.control_client = control_client
        self.control_channel = protocol.YardControlChannel()

    def get_settings(self):
        # TODO Create Settings
        path = 'settings/client.json'
        if os.path.exists(path):
            with open(path, 'r') as f:
                self.settings = json.load(f)
        else:
            with open(path, 'w') as f:
                f.write(json.dumps(self.defaultSettings))
                self.settings = self.defaultSettings

    def init(self) -> str:
        self.get_settings()
        return self.send_init()

    def send_receive(self, ses: int, typ: int, data: Union[str, bytes]) -> Tuple[dict, str]:
        """
        :raises ConnectionAbortedError: When there is a problem with the header, the connection is treated as aborted
        :raises TimeoutError: When it doesn't receive an answer in a defined time-period
        :raises OverflowError: When there is no answer-code left. So it is waiting for to many answers
        :raises OverflowError: When Parameters could not be converted to their byte-representation
        """
        package = self.control_channel.send_receive(self.control_client, ses, typ, data)
        logging.getLogger('yard_client.protocol.conn').debug(
            "Received data from {}:{} | Header: {} || Payload: {}".format(*self.control_socket, *package))
        return package

    def send_ac(self, ses: int, typ: int, data: Union[str, bytes]) -> int:
        """
        Send a message and return the access code.

        :param ses: int: The desired session
        :param typ: int: The desired message type
        :param data: str | bytes: The payload
        :return: int: The access code
        :raises OverflowError: When there is no answer-code left. So it is waiting for to many answers
        :raises OverflowError: When Parameters could not be converted to their byte-representation
        """
        return self.control_channel.send_ac(self.control_client, ses, typ, data)

    def receive_ac(self, ac: int) -> Tuple[dict, str]:
        """
        Receive a message by an access code.

        :param ac: int: The access code
        :return: list: [header, payload]
        :raises ConnectionAbortedError: When there is a problem with the header, the connection is treated as aborted
        :raises TimeoutError: When it doesn't receive an answer in a defined time-period
        """
        package = self.control_channel.receive_ac(self.control_client, ac)
        logging.getLogger('yard_client.protocol.conn').debug(
            "Received data from {}:{} | Header: {} || Payload: {}".format(*self.control_socket, *package))
        return package

    def connect(self):
        logging.getLogger('yard_client.protocol.conn').info("Connecting to {}:{}".format(*self.control_socket))
        self.control_client.connect(self.control_socket)
        self.is_connected = True

    def send_init(self) -> str:
        logging.getLogger('yard_client.protocol.send').debug(f"Sending INIT message to {self.control_socket}")
        return self.send_receive(0, self.control_channel.INIT, self.settings['fingerprint'])[1]

    def ping(self) -> Tuple[dict, str]:
        logging.getLogger('yard_client.protocol.send').debug(f"Sending PING message to {self.control_socket}")
        return self.send_receive(0, self.control_channel.PING, "")

    def req_client(self, client_id: str, trans_clt: YardTransmission) -> Tuple[int, Tuple[str, Union[str, int]]]:
        logging.getLogger('yard_client.protocol.send').debug(f"Sending REQ message to {self.control_socket}")
        password = secrets.token_hex()
        msg = f"{client_id} {password}"
        ac = self.send_ac(0, self.control_channel.REQ, msg)
        trans_clt.send_server_ping(password)
        trans_clt.send_server_ping(password)
        header, data = self.receive_ac(ac)
        data = str(data).split(' ')
        if len(data) == 3:
            session, ip, port = data
            return int(session), (ip, port)
        return 0, ('', 0)

    def send_to_client(self, session: int, message: str):
        # TODO: check if session
        logging.getLogger('yard_client.protocol.send').debug(f"Sending CONN message to {self.control_socket}: {message}")
        self.send_receive(session, self.control_channel.CONN, message)

    def terminate_session(self, session: int):
        # TODO: Delete session
        logging.getLogger('yard_client.protocol.send').debug(f"Sending TERM message to {self.control_socket}")
        self.send_receive(session, self.control_channel.TERM, "")

    def renew(self) -> str:
        logging.getLogger('yard_client.protocol.send').debug(f"Sending REN message to {self.control_socket}")
        return self.send_receive(0, self.control_channel.REN, self.settings['fingerprint'])[1]

    def send_err(self, message):
        # TODO: Send err to client
        pass

    def send_warn(self, message):
        # TODO: Send warn to client
        pass

    def close(self):
        # TODO: Delete sessions, close server connection
        logging.getLogger('yard_client.protocol.send').debug(f"Sending CLOSE message to {self.control_socket}")
        self.control_channel.send(self.control_client, self.control_channel.CLOSE, "")
        self.control_client.close()     # Close socket
        self.control_channel.close()    # Stop internal timers, stop timeouts
