import math
import pickle
import socket
import logging
import threading
import time
from typing import Union, Tuple, Any, Callable, Literal

import numpy as np

from protocol import protocol


class YardTransmission:
    transmission_socket = None
    transmission_target = None
    transmission_server = None
    transmission_client = None
    transmission_channel = None

    public_sock = None
    private_sock = None

    udp_pass = None
    udp_packages = None
    image_parent = 0
    encoding = 'utf-8'
    byte_order: Literal["little", "big"] = 'little'
    dgram_size = 1000

    package_wait = 1

    receiving = False
    stopping = False

    def __init__(self, transmission_socket, transmission_target, transmission_server,
                 transmission_client: socket.socket, buffer: int):
        init_logger = logging.getLogger('yard_client.transmission.init')
        init_logger.debug("Initializing Transmission client")
        self.transmission_socket = transmission_socket
        self.transmission_target = transmission_target
        self.transmission_server = transmission_server
        self.transmission_client = transmission_client
        self.transmission_channel = protocol.YardTransmissionChannel()
        self.transmission_channel.buffer = buffer
        self.transmission_channel.data_len = buffer - self.transmission_channel.header_len
        self.transmission_client.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, buffer)
        self.transmission_client.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, buffer)
        self.last_send = time.time()
        self.sent = 0

    def get_public_sock(self):
        return self.public_sock

    def get_private_sock(self):
        return self.transmission_client.getsockname()

    def connect(self):
        self.transmission_client.bind(self.transmission_socket)
        self.transmission_socket = self.transmission_client.getsockname()

    def punch_udp_hole(self, sock, udp_pass):
        def send(hello_event: threading.Event):
            while not hello_event.is_set():
                self.send_raw(sock, udp_pass)
                time.sleep(2)
            for i in range(10):
                self.send_raw(sock, udp_pass)

        event = threading.Event()
        thread = threading.Thread(target=send, args=[event])
        thread.start()
        # Until it gets an answer
        while not self.stopping:
            try:
                pkg = self.receive_raw()
                if str(pkg[0], self.transmission_channel.encoding) == self.udp_pass and pkg[1] == sock:
                    self.transmission_target = sock
                    event.set()
                    break
            except:
                pass

    def send_server_ping(self, password: Union[str, bytes]):
        self.send_raw(self.transmission_server, password)

    def send(self, typ: int, data: Union[str, bytes]):
        """
        :raises OverflowError: When there is no answer-code left. So it is waiting for to many answers
        """
        self.transmission_channel.send(self.transmission_client, self.transmission_target, typ, data)

    def send_raw(self, target: Tuple[Any, ...] | str, data: Union[str, bytes]):
        logging.getLogger('yard_client.transmission.send').debug(
            f"Sending raw message to {target}")
        self.transmission_channel.send_raw(self.transmission_client, target, data)

    def send_close(self):
        logging.getLogger('yard_client.transmission.send').debug(f"Sending CLOSE message to {self.transmission_socket}")
        self.send(self.transmission_channel.CLOSE, "")

    def send_display(self, img: np.ndarray):
        send_logger = logging.getLogger('yard_client.transmission.send')
        send_logger.debug(f"Sending DISPLAY to {self.transmission_target}")

        if time.time() - self.last_send > 10:
            self.last_send = time.time()
            send_logger.debug(
                f"Sending display with {self.sent // 10} FPS")
            self.sent = 0

        data = img.tobytes()   # TODO Check if needed
        size = len(data)
        count = math.ceil(size / self.dgram_size)

        array_pos_start = 0
        for i in range(count-1, -1, -1):
            array_pos_end = min(size, array_pos_start + self.dgram_size)
            pkg = pickle.dumps((i, data[array_pos_start:array_pos_end]))
            array_pos_start = array_pos_end
            self.send(self.transmission_channel.DISPLAY, pkg)
            time.sleep(0.000001)
        self.sent += 1

    def send_key(self, data):
        logging.getLogger('yard_client.transmission.send').debug(
            f"Sending KEY message to {self.transmission_target}")
        self.send(self.transmission_channel.KEY, data)

    def receive(self, callback: Callable[[Tuple[dict, bytes, Any]], Any]):
        pkg = self.transmission_channel.receive(self.transmission_client)
        logging.getLogger('yard_client.transmission.receive').debug(
            f"Received {self.transmission_channel.types[pkg[0]['typ']]} message from {pkg[2]}:")
        callback(pkg)

    def receive_key(self, callback: Callable[[dict, 'Input', Any], Any]):
        def receive_parts():
            while not self.stopping or not self.receiving:
                pkg = None
                try:
                    pkg = self.transmission_channel.receive(
                        self.transmission_client)
                except Exception as e:
                    logging.getLogger('yard_client.transmission.receive').warning(e)

                if pkg:
                    # TODO: Check if correct address als top level like a filter bind udp to address maybe
                    header, payload, address = pkg
                    if header['typ'] == self.transmission_channel.KEY:
                        callback(header, pickle.loads(payload), address)  # TODO Could be dangerous pickle.loads

            self.receiving = False

        if not self.receiving:
            self.receiving = True
            thread = threading.Thread(target=receive_parts)
            thread.start()

    def receive_display(self, callback: Callable[[Tuple[dict, bytes, Any]], Any]):
        fragments = {}

        def handle_parts(pkg):
            nonlocal fragments
            header, payload, address = pkg
            if header['typ'] == self.transmission_channel.DISPLAY:
                pkg_data = pickle.loads(payload)
                if pkg_data[0] >= 1:
                    fragments[pkg_data[0]] = pkg_data[1]
                else:
                    fragments[pkg_data[0]] = pkg_data[1]
                    data = b''.join([x[1] for x in sorted(fragments.items(), reverse=True)])
                    fragments = {}
                    callback((header, data, address))

        def receive_parts():
            while not self.stopping or not self.receiving:
                try:
                    pkg = self.transmission_channel.receive(
                        self.transmission_client)  # TODO: Check if correct address als top level like a filter bind udp to address maybe
                    thread_part = threading.Thread(target=handle_parts, args=[pkg])
                    thread_part.start()
                except Exception as e:
                    logging.getLogger('yard_client.transmission.receive').exception(e)

            self.receiving = False

        if not self.receiving:
            self.receiving = True
            thread = threading.Thread(target=receive_parts)
            thread.start()

    def receive_raw(self) -> Tuple[bytes, Any]:
        pkg = self.transmission_channel.receive_raw(self.transmission_client)
        logging.getLogger('yard_client.transmission.receive').debug(
            f"Received {pkg[0]} from {pkg[1]}:")
        return pkg

    def close(self):
        # TODO: Delete sessions, close server connection
        self.stopping = True
        self.send_close()
        self.transmission_client.close()
