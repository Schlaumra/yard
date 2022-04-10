import json
import logging
import pickle
import socket
import threading
import time
import uuid
from typing import Tuple, Any

import cv2
import mss
import numpy as np
from PIL import ImageTk, Image

from display.mainwindow import MainWindow
from objects import secret
from objects.connectionobj import ConnectionObj
from objects.inputobj import Input, Key, Mouse
from objects.storage import ConnectionStorage
from protocol.yardclient import YardClient
from protocol.yardtransmission import YardTransmission
from pynput.keyboard import Controller as KeyController
from pynput.mouse import Controller as MouseController

conf = json.load(open('settings/conf.json'))


# TODO: If client renews while connecting broken pipe after failed connect (on server an exception happens)

# TODO: Send router ip not local ip
# TODO: Check re-login is not working


class ClientDaemon:
    TERM = 'TERM'
    INIT = 'INIT'
    ACC = 'ACC'
    WARN = 'WARN'
    ERR = 'ERR'

    default_ping_wait = 5  # multiply by 2 to get max wait time
    ping_wait = default_ping_wait
    password_len = conf['server']['password_len']
    server_socket = (conf['server']['hostname'], conf['server']['port'])
    transmission_buffer = conf['transmission']['buffer']
    clt_conn = None
    clt_public_ip = None
    clt = None
    clt_id = None
    clt_pass = None
    ping_loop_event = None
    stopping = False

    connection_storage = None
    pending_connections = None

    capture = None
    keyboard: KeyController = None
    mouse: MouseController = None

    main_window = None

    def __init__(self):
        logging.getLogger('yard_client.starting').info("Starting YardClient ...")
        self.clt_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clt = YardClient(self.server_socket, self.clt_conn)
        self.connection_storage = ConnectionStorage()
        self.pending_connections = {}
        self.ping_loop_event = threading.Event()

    def connect(self):
        self.connection_storage.add_connection('root', 0, True)
        if not self.clt.is_connected:
            self.clt.connect()

    def get_client_info(self, *, pending_session: int = None, pending_password: str = None,
                        conn: ConnectionObj = None) -> str:
        fingerprint = uuid.UUID(self.clt.settings['fingerprint'])
        client_id = self.clt_id
        if pending_session is not None:
            password = input("Enter password for client: ")
            pending_password = self.clt_pass = secret.create_secret(32, alphabet=(True, True))
            self.pending_connections[pending_session] = {}
            ses = self.pending_connections[pending_session]
            ses['pend_pass'] = pending_password
            ses['connection'] = self.connection_storage.get_connection_by_ses(pending_session)
            ses['connection'].transmission.udp_pass = udp_pass = secret.create_secret(32, alphabet=(True, True))
            public_sock_ip, public_sock_port = ses['connection'].transmission.get_public_sock()
            return f"{fingerprint} {client_id} " \
                   f"{public_sock_ip} {public_sock_port} " \
                   f"{password} {pending_password} " \
                   f"{udp_pass}"
        elif pending_password is not None and conn is not None:
            public_sock_ip, public_sock_port = conn.transmission.get_public_sock()
            conn.transmission.udp_pass = udp_pass = secret.create_secret(32, alphabet=(True, True))
            return f"{fingerprint} {client_id} " \
                   f"{public_sock_ip} {public_sock_port} " \
                   f"{pending_password} " \
                   f"{udp_pass}"
        else:
            raise SyntaxError("Not all correct parameters are passed")

    def answer_ping_message(self, header: dict, message: str):
        ping_logger = logging.getLogger('yard_client.ping')
        try:
            match message.split():
                case cmd, *args:
                    match cmd:
                        # On receiving client (Object -> Asked to be connected to)
                        case self.INIT:
                            if len(args) == 7:
                                fingerprint, client_id, public_ip, public_port, password, pending_password, udp_pass = args
                                public_port = int(public_port)
                                public_sock = (public_ip, public_port)
                                # ATTENTION: IF password correct you could use it as an amplification attack
                                fingerprint = uuid.UUID(fingerprint)
                                if password == self.clt_pass:
                                    trans_clt = self.create_udp_session()
                                    ses, pub_sock = self.clt.req_client(client_id, trans_clt)
                                    if ses and header['ses'] == ses and pub_sock:
                                        trans_clt.public_sock = pub_sock
                                        cs_id = self.connection_storage.add_connection(client_id,
                                                                                       ses,
                                                                                       True,
                                                                                       fingerprint=fingerprint,
                                                                                       transmission=trans_clt)
                                        ping_logger.info(f"Client [{public_ip}:{fingerprint}] connected successfully.")

                                        connection = self.connection_storage.connections[cs_id]
                                        self.send_accept_to_client(header['ses'], pending_password, connection)
                                        trans_clt.punch_udp_hole(public_sock, udp_pass)

                                        ping_logger.info("Receiving transmission data")
                                        self.start_key_receiver(connection)

                                        ping_logger.info(f"Start sending Display to {trans_clt.transmission_target}")
                                        thread = threading.Thread(target=self.send_display, args=[connection])
                                        thread.start()

                                        # TODO: Start sending display
                                        # TODO: Start receiving keys
                                        # while True:
                                        #     msg = bytes(input("send>"), 'utf-8')
                                        #     trans_session.send_display(msg)
                                        self.ping_wait = self.default_ping_wait
                                else:
                                    # TODO: On second client wrong password
                                    ping_logger.warning("Wrong password, terminating connection.")
                                    self.ping_wait = self.default_ping_wait
                                    self.clt.send_to_client(
                                        header['ses'],
                                        self.TERM + " " + "Not permitted")
                        case self.TERM:
                            self.ping_wait = self.default_ping_wait
                            ping_logger.info("Session terminated: " + ' '.join(args))
                        case self.ACC:
                            # On sending client (Subject -> Wants to connect)
                            if len(args) == 6:
                                fingerprint, client_id, public_ip, public_port, pending_password, udp_pass = args
                                public_port = int(public_port)
                                public_sock = (public_ip, public_port)
                                fingerprint = uuid.UUID(fingerprint)
                                if header['ses'] in self.pending_connections.keys():
                                    if self.pending_connections[header['ses']]['pend_pass'] == pending_password:
                                        ping_logger.info(f"Client [{public_ip}:{fingerprint}] connected successfully.")
                                        trans_session: YardTransmission = self.pending_connections[header['ses']][
                                            'connection'].transmission
                                        trans_session.punch_udp_hole(public_sock, udp_pass)
                                        cs_id = self.connection_storage.add_connection(
                                            client_id, header['ses'],
                                            True,
                                            fingerprint=fingerprint,
                                            transmission=trans_session)

                                        connection = self.connection_storage.connections[cs_id]
                                        ping_logger.info("Receiving transmission data")
                                        connection.transmission.receive_display(self.handle_display)

                                        ping_logger.info("Start sending keys")
                                        thread = threading.Thread(target=self.start_gui, args=[connection])
                                        thread.start()

                                        # TODO: Start sending keys
                                        # TODO: Receive Display
                                        # while True:
                                        #     msg = bytes(input("send>"), 'utf-8')
                                        #     trans_session.send_display(msg)
                                        self.ping_wait = self.default_ping_wait
                                    else:
                                        ping_logger.warning(
                                            "Wrong pending_password, but correct fingerprint, terminating connection.")
                                        self.ping_wait = self.default_ping_wait
                                        self.clt.send_to_client(
                                            header['ses'],
                                            self.TERM + " " + "Not permitted")
                                else:
                                    ping_logger.warning("Not waiting for that connection, terminating connection")
                                    self.ping_wait = self.default_ping_wait
                                    self.clt.send_to_client(
                                        header['ses'],
                                        self.TERM + " " + "Not permitted")
                            self.ping_wait = self.default_ping_wait
                            ping_logger.info("Session accepted")
                        case self.WARN:
                            ping_logger.warning(f"Client received a warning from {header}: {''.join(args)}")
                        case self.ERR:
                            ping_logger.warning(f"Client received a error from {header}: {''.join(args)}")
                            # TODO: Throw exception
                            raise Exception
                        case _:
                            ping_logger.warning(f"Client received unknown command {message}")
                case _:
                    ping_logger.warning(f"Client received unknown ping message {message}")
        except Exception as e:
            ping_logger.exception(e)

    def send_init_to_client(self, ses: int):
        self.clt.send_to_client(ses, "INIT " + self.get_client_info(pending_session=ses))
        self.ping_wait = 1

    def send_accept_to_client(self, ses: int, pending_password: str, connection: ConnectionObj):
        self.clt.send_to_client(
            ses,
            self.ACC
            + " "
            + self.get_client_info(pending_password=pending_password,
                                   conn=connection))
        self.ping_wait = 1

    def reset(self):
        # TODO: Reset everything
        # TODO: close sessions
        temp = self.clt.renew()
        if temp:
            temp_id, temp_ip = temp.split()
            self.clt_id = temp_id
            self.clt_public_ip = temp_ip
            self.clt_pass = secret.create_secret(self.password_len, alphabet=(True, True))
            logging.getLogger('yard_client.reset').info(
                "ID: %s === Password: %s === IP: %s" % (self.clt_id, self.clt_pass, self.clt_public_ip))

    def start(self, events: dict = None):
        main_logger = logging.getLogger('yard_client.main')
        # TODO Implement events
        temp = self.clt.init()
        if temp:
            temp_id, temp_ip = temp.split()
            self.clt_id = temp_id
            self.clt_public_ip = temp_ip
            self.clt_pass = secret.create_secret(self.password_len, alphabet=(True, True))
            main_logger.info("ID: %s === Password: %s === IP: %s" % (self.clt_id, self.clt_pass, self.clt_public_ip))
        thread = threading.Thread(target=self.ping_loop)
        main_logger.debug("Client starts new thread")
        thread.start()

    def ping_loop(self):
        while not self.ping_loop_event.is_set():
            pkg = self.clt.ping()
            if pkg[1]:
                self.answer_ping_message(*pkg)
            self.ping_loop_event.wait(self.ping_wait)

    def connect_to_client(self, client_id) -> int:
        trans_clt = self.create_udp_session()
        ses, pub_sock = self.clt.req_client(client_id, trans_clt)  # TODO: Retry if failed
        if ses and pub_sock:
            trans_clt.public_sock = pub_sock
            self.connection_storage.add_connection(client_id, ses, True, transmission=trans_clt)
            self.send_init_to_client(ses)
            return ses
        else:
            # TODO: Create Exceptions
            self.connection_storage.add_connection(client_id, 0, False)
            raise Exception("Client does not exist")

    def close(self):
        # TODO: close sessions
        self.clt.close()
        self.stopping = True
        self.ping_loop_event.set()

    def handle_display(self, display: Tuple[dict, bytes, Any]):
        data = display[1]
        try:
            img = cv2.imdecode(np.fromstring(data, dtype=np.uint8), 1)
            if img is not None:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(img, mode="RGB")
                img = ImageTk.PhotoImage(image=img)
                self.main_window.stream_frame.config(image=img)
                self.main_window.stream_frame.image = img
        except Exception as e:
            logging.getLogger('yard_client.receive_display').exception(e)

    def start_key_receiver(self, connection: ConnectionObj):
        self.keyboard = KeyController()
        self.mouse = MouseController()
        connection.transmission.receive_key(self.handle_key)

    def handle_key(self, header: dict, key: Input, address: Any):
        key_logger = logging.getLogger('yard_client.receive_key')   # TODO: Release key if to long
        if isinstance(key, Key):
            try:
                if key.state:
                    self.keyboard.press(key.get_command())
                else:
                    self.keyboard.release(key.get_command())
            except ValueError as e:
                key_logger.warning(f"Unknown Key: {e}")
        elif isinstance(key, Mouse):
            if key.coordinates:
                self.mouse.position = key.coordinates
                if key.scroll:
                    self.mouse.scroll(*key.scroll)
                elif key.get_command():
                    self.mouse.press(key.get_command())
                    if not key.drag:
                        self.mouse.release(key.get_command())

    def start_gui(self, connection: ConnectionObj):

        def send_keys(input_obj: Input):
            nonlocal connection
            connection.transmission.send_key(pickle.dumps(input_obj))

        if not self.main_window:
            self.main_window = MainWindow(send_keys)
            self.main_window.start()

    def send_display(self, connection: ConnectionObj):
        self.capture = mss.mss()
        while True:
            img = np.array(self.capture.grab(self.capture.monitors[0]))
            connection.transmission.send_display(cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 30])[1])
            time.sleep(0.001)

    def create_udp_session(self) -> YardTransmission:
        clt_conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        trans_clt = YardTransmission(('0.0.0.0', 0), None, self.server_socket, clt_conn, self.transmission_buffer)
        trans_clt.connect()
        return trans_clt
