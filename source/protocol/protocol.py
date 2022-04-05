import logging
import socket
import time
from threading import Timer
from typing import Union, Literal, Dict, Tuple, Any


class YardControlChannel:
    """
    Control Channel Protocol for communication between server and client.

    YardControlChannel() -> YardControlChannel

    Types
    -----------
    'CLOSE': 0x00
    'INIT': 0x01
    'PING': 0x02
    'REQ': 0x03
    'CONN': 0x04
    'TERM': 0x05
    'REN': 0x06
    'ANS': 0x07
    'ERR': 0x08
    'WARN': 0x09

    Package definition
    -----------
    pkg = [{'ver': version_number, 'ses': session_number, 'typ': message_type, 'len': length_of_payload}, payload]
    """
    version: int = 0
    header_len: int = 6
    receive_timeout = 10
    encoding = "utf-8"
    byteorder: Literal['little', 'big'] = 'little'

    types = ['CLOSE', 'INIT', 'PING', 'REQ', 'CONN', 'TERM', 'REN', 'ANS', 'ERR', 'WARN']

    CLOSE = 0x00
    INIT = 0x01
    PING = 0x02
    REQ = 0x03
    CONN = 0x04
    TERM = 0x05
    REN = 0x06
    ANS = 0x07
    ERR = 0x08
    WARN = 0x09

    cached_packages: Dict[int, Tuple[dict, str]] = None
    waiting_ac: list = None
    timers: list = None

    def __init__(self):
        self.cached_packages = {}
        self.waiting_ac = []
        self.timers = []

    def convert_to_bytes(self, data: Union[str, bytes]) -> bytes:
        """
        Ensure that data is in byte form.

        :param data: str ⌈ bytes: The input
        :return: bytes: The output
        """
        return data if type(data) == bytes else bytes(data, self.encoding)

    def create_header(self,
                      ses: int,
                      typ: int,
                      *,
                      ac: int = 0,
                      pl: Union[bytes, str] = b"",
                      ver: int = None,
                      length: int = None) -> dict:
        """
        Create the protocol header.

        In order to communicate between client and server you need to create a header.
        You can prepare the header here and use it later.

        {'ver': int, 'ses': int, 'ac': int, 'typ': int, 'len': int}

        :param ses: int: number of desired session
        :param typ: int: number of the message type see 'self.types'
        :param ac: int(Optional, keyword-only): Answer code of message
        :param pl: bytes | str (Optional, keyword-only): payload of message
        :param ver: int(Optional, keyword-only): Instead of predefined version pass desired version number
        :param length: int(Optional, keyword-only): Instead of payload pass the desired length
        :return: dict: {'ver': version_number, 'ses': session_number, 'typ': message_type, 'len': length_of_payload}
        :raises OverflowError: When Parameters could not be converted to their byte-representation
        and are therefore to long for the header
        """
        pl = self.convert_to_bytes(pl)
        length = length or len(pl)

        if ses.bit_length() <= 8 and typ.bit_length() <= 8 and length.bit_length() <= 16:
            return {'ver': ver or self.version, 'ses': ses, 'ac': ac, 'typ': typ, 'len': length}
        else:
            raise OverflowError("Bit-length of one or more parameters to long; Header could not be created")

    def create_byte_header(self, header: dict) -> bytes:
        """
        Prepare header for sending.

        Normally you use directly 'self.send()'

        :param header: dict: Header created by 'create_header()'
        :return: bytes: b'\\x01\\x01\\x01\\0x01\\x05\\x00'
        """

        # Convert int to bytes and concatenate
        return (int(header['ver']).to_bytes(1, self.byteorder)
                + int(header['ses']).to_bytes(1, self.byteorder)
                + int(header['typ']).to_bytes(1, self.byteorder)
                + int(header['ac']).to_bytes(1, self.byteorder)
                + int(header['len']).to_bytes(2, self.byteorder))

    def send(self, sock: socket.socket, typ: int, data: Union[str, bytes], *, ses: int = 0, ac: int = 0) -> None:
        """
        Send a package to the given socket.

        :param sock: socket.socket: The socket where to send the package
        :param ses: int: The desired session
        :param typ: int: The desired message type
        :param data: str | bytes: The payload
        :param ac: str(Optional, keyword-only): If answer add answer code
        :return: None
        :raises OverflowError: When Parameters could not be converted to their byte-representation
        """

        # Ensure that data is in byte-form
        data = self.convert_to_bytes(data)
        # Send header and payload
        sock.send(self.create_byte_header(self.create_header(ses, typ, pl=data, ac=ac)))
        sock.send(data)

    def receive(self, sock: socket.socket) -> Tuple[dict, str]:
        """
        Receive a package from the client.

        Socket needs to be initialized and bound.

        :param sock: socket.socket: The socket where it receives the package
        :return: tuple: (header, payload)
        :raises ConnectionAbortedError: When there is a problem with the header, the connection is treated as aborted
        """
        header = {}
        payload = ""

        # Receive the header as data
        data = sock.recv(self.header_len)
        if data:
            try:
                # Convert to header
                header = self.create_header(ver=data[0],
                                            ses=data[1],
                                            typ=data[2],
                                            ac=data[3],
                                            length=int.from_bytes(data[4:], self.byteorder))
                if header['ver'] != self.version:
                    raise Exception     # TODO: Create Version exception
                if header['typ'] >= len(self.types):
                    raise Exception     # TODO: Create type not recognised
            except OverflowError as e:
                raise ConnectionAbortedError(e)
        if not header:
            raise ConnectionAbortedError("Connection has been aborted due to missing header")
        else:
            # Get payload
            if header['len'] > 0:
                payload = str(sock.recv(header['len']).decode(self.encoding))
        return header, payload

    def send_receive(self, sock: 'socket.socket', ses: int, typ: int, data: Union[str, bytes]) -> Tuple[dict, str]:
        """
        Send a message and wait for the corresponding answer.

        :param sock: socket.socket: The socket where it sends and receives the package
        :param ses: int: The desired session
        :param typ: int: The desired message type
        :param data: str | bytes: The payload
        :return: list: [header, payload]
        :raises ConnectionAbortedError: When there is a problem with the header, the connection is treated as aborted
        :raises TimeoutError: When it doesn't receive an answer in a defined time-period
        :raises OverflowError: When there is no answer-code left. So it is waiting for to many answers
        :raises OverflowError: When Parameters could not be converted to their byte-representation
        """
        # Send the message and get access code
        ac = self.send_ac(sock, ses, typ, data)
        # Receive message
        return self.receive_ac(sock, ac)

    def get_access_code(self) -> int:
        """
        Get a free access code.

        :return: int: The access code
        :raises OverflowError: When there is no answer-code left. So it is waiting for to many answers
        """
        # Get free access code
        for i in range(1, 256):
            if not self.waiting_ac.count(i):
                ac = i
                self.waiting_ac.append(ac)
                return ac
        else:
            raise OverflowError("No answer-code left")

    def send_ac(self, sock: 'socket.socket', ses: int, typ: int, data: Union[str, bytes]) -> int:
        """
        Send a message and return the access code.

        :param sock: socket.socket: The socket where it sends the package
        :param ses: int: The desired session
        :param typ: int: The desired message type
        :param data: str | bytes: The payload
        :return: int: The access code
        :raises OverflowError: When there is no answer-code left. So it is waiting for to many answers
        :raises OverflowError: When Parameters could not be converted to their byte-representation
        """
        ac = self.get_access_code()

        # Send the message
        self.send(sock, typ, data, ses=ses, ac=ac)

        return ac

    def receive_ac(self, sock: 'socket.socket', ac) -> Tuple[dict, str]:
        """
        Receive a message by an access code.

        :param sock: socket.socket: The socket where it sends and receives the package
        :param ac: int: The access code
        :return: list: [header, payload]
        :raises ConnectionAbortedError: When there is a problem with the header, the connection is treated as aborted
        :raises TimeoutError: When it doesn't receive an answer in a defined time-period
        """
        timeout = False

        # Function to tell when timeout is over
        def start_timeout():
            nonlocal timeout
            timeout = True

        # Start timeout
        timer = Timer(self.receive_timeout, start_timeout)
        self.timers.append(timer)
        timer.start()

        # As long as no timeout -> wait for answer
        while not timeout:
            # If already in cache return
            cached = self.cached_packages.get(ac, None)
            if cached:
                timer.cancel()
                return cached

            # Receive a package
            pkg = self.receive(sock)

            # If access code corresponds to the requested
            if pkg[0]['ac'] == ac:
                self.waiting_ac.remove(ac)
                return pkg
            else:
                # Cache the package
                self.cached_packages[pkg[0]['ac']] = pkg
        else:
            # Timeout exceeded
            self.waiting_ac.remove(ac)
            raise TimeoutError("Waited to long for answer")

    def close(self) -> None:
        """
        Close the protocol and all it's threads

        :return: None
        """
        for timer in self.timers:
            timer.cancel()


class YardTransmissionChannel:
    """
    Transmission Channel Protocol for communication between client and client.

    YardTransmissionChannel() -> YardTransmissionChannel

    Types
    -----------
    'CLOSE': 0x00
    'DISPLAY': 0x01
    'KEY': 0x02

    Package definition
    -----------
    pkg = {'ver': version_number, 'typ': session_number, 'parent': parent_number 'payload': payload}
    """
    version: int = 0
    header_len = 5
    buffer: int = 1024
    data_len: int = buffer - header_len
    mtu: int = 65000
    encoding = "utf-8"
    byteorder: Literal['little', 'big'] = 'little'

    types = ['CLOSE', 'DISPLAY', 'KEY']

    CLOSE = 0x00
    DISPLAY = 0x01
    KEY = 0x02

    parent = 0
    last_send = time.time()
    wait = 0.07
    package_timeout = 3

    def convert_to_bytes(self, data: Union[str, int, bytes], byte_len: int = 1) -> bytes:
        """
        Ensure that data is in byte form.

        :param byte_len: int: The byte-length (for int)
        :param data: str|int|bytes: The input
        :return: bytes: The output
        """
        if type(data) == bytes:
            return data
        if type(data) == int:
            return data.to_bytes(byte_len, self.byteorder)
        if type(data) == str:
            return bytes(data, self.encoding)

    def create_header(self,
                      typ: int,
                      *,
                      ver: int = None) -> dict:
        """
        Create the protocol header.

        You can prepare the header here and use it later.

        {'ver': int, 'typ': int, 'par': int, 'mis': int}

        :param typ: int: number of the message type see 'self.types'
        :param ver: int(Optional, keyword-only): Instead of predefined version pass desired version number
        :return: dict: {'ver': version_number, 'typ': message_type}
        :raises OverflowError: When Parameters could not be converted to their byte-representation
        and are therefore to long for the header
        """
        if typ.bit_length() <= 8:
            return {'ver': ver or self.version, 'typ': typ}
        else:
            raise OverflowError("Bit-length of one or more parameters to long; Header could not be created")

    def create_byte_header(self, header: dict) -> bytes:
        """
        Prepare header for sending.

        Normally you use directly 'self.send()'

        :param header: dict: Header created by 'self.create_header()'
        :return: bytes: b'\\x01\\x01\\x11\\x02\\0x00'
        """

        # Convert int to bytes and concatenate
        return (self.convert_to_bytes(header['ver'])
                + self.convert_to_bytes(header['typ']))

    def send(self,
             sock: socket.socket,
             target: Tuple[Any, ...] | str,
             typ: int, data: Union[str, bytes]) -> None:
        """
        Send a package to the given socket.

        :param sock: socket.socket: The socket where to send the package
        :param target:
        :param typ: int: The desired message type
        :param data: str | bytes: The payload
        :return: None
        :raises OverflowError: When Parameters could not be converted to their byte-representation
        """

        # Ensure that data is in byte-form
        data = self.convert_to_bytes(data)

        if len(data) >= self.data_len or len(data) >= self.mtu:
            raise OverflowError("Data to long for udp package")
        sock.sendto(
            self.create_byte_header(
                self.create_header(typ=typ)) + data, target)

    def send_raw(self, sock: socket.socket, target: Tuple[Any, ...] | str, data: Union[str, bytes]) -> None:
        """
        Send a raw package to the given socket. (Without header)

        :param sock: socket.socket: The socket where to send the package
        :param target:
        :param data: str | bytes: The payload
        :return: None
        :raises OverflowError: When Parameters could not be converted to their byte-representation
        """
        # Ensure that data is in byte-form
        data = self.convert_to_bytes(data)

        # Send package
        sock.sendto(data, target)

    def receive(self, sock: socket.socket) -> Tuple[dict, bytes, Any]:
        """
        Receive a package from the client.

        Socket needs to be initialized and bound.

        :param sock: socket.socket: The socket where it receives the package
        :return: Tuple: ({'ver': version_number, 'typ': type_number, 'par': parent, 'pos': position}, 'payload': payload, 'address': address)
        :raises ConnectionAbortedError: When there is a problem with the data, the connection is treated as aborted
        """

        # Receive the data and convert it to a package
        data, address = sock.recvfrom(self.buffer)
        if data:
            header = self.create_header(typ=data[1],
                                        ver=data[0])
            payload = data[2:]
            pkg = header, payload, address
            if header['ver'] != self.version:
                raise Exception     # TODO: Create Exception
            if header['typ'] >= len(self.types):
                raise Exception     # TODO: Create Exception
            return pkg
        else:
            raise ConnectionAbortedError("Connection has been aborted due to missing header")

    # def receive_all(self,
    #                 sock,
    #                 parent: int = None,
    #                 found_last: bool = False,
    #                 old_packages: list = None) -> Tuple[dict, bytes, Any]:
    #     pkg = self.receive(sock)
    #     header, pkg_data, source = pkg
    #     data = None
    #
    #     if not old_packages:
    #         old_packages = []
    #         # package = {'received', 'data', 'parent'}
    #
    #     for package in reversed(old_packages):
    #         if time.time() - package['received'] >= self.package_timeout:
    #             old_packages.remove(package)
    #         elif package['parent'] == header['par']:
    #             print(package['parent'])
    #             data = package['data']
    #             break
    #
    #     if not data:
    #         data = {header['pos']: pkg}
    #     else:
    #         print(data.keys())
    #         data[header['pos']] = pkg
    #
    #     # If received last but not found all yet
    #     if found_last and parent and header['par'] == parent:
    #         found_last = False
    #
    #     if header['pos'] > 0 and not found_last:
    #         if not parent or header['par'] == parent:
    #             return self.receive_all(sock, header['par'], old_packages=old_packages)
    #         elif parent:
    #             old_packages.append({'received': time.time(), 'data': {header['mis']: pkg}, 'parent': header['par']})
    #             return self.receive_all(sock, header['par'], old_packages=old_packages)
    #         else:
    #             raise Exception("Something went wrong while receiving")
    #     elif header['mis'] == 0 or found_last:
    #         if not parent or header['par'] == parent:
    #             if len(data)-1 == max(data.keys()):
    #                 result = b''.join(x[1] for x in data.values())
    #                 return header, result, source
    #             else:
    #                 return self.receive_all(sock, header['par'], found_last=True)
    #         elif parent:
    #             return header, pkg_data, source
    #         else:
    #             raise Exception("Something went wrong while receiving")
    #     else:
    #         raise Exception("Something went wrong while receiving")

    def receive_raw(self, sock: socket.socket, buffer: int = 1024) -> Tuple[bytes, Any]:
        """
        Receive a raw package from the client. (Without Header)

        Socket needs to be initialized and bound.

        :param sock: socket.socket: The socket where it receives the package
        :param buffer: The desired buffer
        :return: Tuple: ('data': data, 'address': address)
        :raises ConnectionAbortedError: When there is a problem with the data, the connection is treated as aborted
        """

        # Receive the data and convert it to a package
        data, address = sock.recvfrom(buffer)
        if data:
            return data, address
        else:
            raise ConnectionAbortedError("Connection has been aborted due to missing header")
