import logging
import socket
import threading
import uuid
from typing import Tuple, Union, Any, List, Dict

from objects.storage import ClientStorage
from protocol.protocol import YardControlChannel, YardTransmissionChannel


class YardServer:
    """
    Class for handling yard client connections.

    YardServer(control_socket, control_server)
    """

    control_socket: Union[Tuple[Any, ...], str] = None
    control_server: socket.socket = None
    control_channel: YardControlChannel = None

    transmission_socket: Union[Tuple[Any, ...], str] = None
    transmission_server: socket.socket = None
    transmission_channel: YardTransmissionChannel = None

    client_storage: ClientStorage = None
    connections: List = None
    timers: List[threading.Timer] = None
    udp_wait_timeout = 10
    udp_save_timeout = 10
    stopping = False

    udp_receive_event: threading.Event = None
    udp_received: Dict[Any, Tuple[str, Union[str, int]]]

    # TODO Create fingerprint check (fingerprint and socket are connected MITM) Send fingerprint encrypted
    # TODO Check if really fingerprint malicious data
    # TODO add timeout to clear connections

    def __init__(self,
                 server_socket: Union[Tuple[Any, ...], str],
                 control_server: socket.socket,
                 transmission_server: socket.socket):

        logging.getLogger('yard_server.init').debug("Initializing Control server")

        self.control_socket = server_socket
        self.control_server = control_server
        self.control_channel = YardControlChannel()

        self.transmission_socket = server_socket
        self.transmission_server = transmission_server
        self.transmission_channel = YardTransmissionChannel()

        self.client_storage = ClientStorage()
        self.connections = []
        self.timers = []
        self.udp_receive_event = threading.Event()
        self.udp_received = {}

        self.control_server.bind(self.control_socket)
        self.transmission_server.bind(self.transmission_socket)

    def send(self, sock: socket.socket, typ: int, *, data: Union[str, bytes] = b"", ses: int = 0, ac: int = 0):
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
        logging.getLogger('yard_server.connection').debug(
            f"Sending answer message to {sock.getpeername()} Message: {data}")
        self.control_channel.send(sock=sock,
                                  ses=ses,
                                  typ=typ,
                                  ac=ac,
                                  data=data)

    def answer_message(self, sock: socket.socket, package: Tuple[dict, str]) -> bool:
        """
        Answer to the received message.

        :param sock: socket.socket The socket where the message came from
        :param package: Tuple[header, payload] The received package
        :return: bool: True -> Continue receiving, False -> Closing client connection
        """
        header, payload = package
        ses: int = header['ses']
        typ: int = header['typ']
        ac: int = header['ac']

        try:
            clt = self.client_storage.get_client_by_socket(sock)
            logging.getLogger('yard_server.connection').info(
                f"Answer to message from {clt.client_id if clt else 'guest'} type: {self.control_channel.types[typ]}")

            if typ == self.control_channel.INIT:
                # raises ValueError: If clients sends not a UUIDv4
                try:
                    clt = self.client_storage.create_client(uuid.UUID(payload), sock=sock)
                except ValueError as e:
                    self.send(sock=sock,
                              typ=self.control_channel.ERR,
                              data="UUID is in the wrong format.")
                    logging.getLogger('yard_server.connection').exception(e)
                    return False
                # Sends the client_id and its public ip and port
                self.send(sock=sock,
                          typ=self.control_channel.ANS,
                          ac=ac,
                          data=f"{clt.client_id} {sock.getpeername()[0]}")
            elif clt and clt.is_initialized(sock):
                match typ:
                    case self.control_channel.CLOSE:
                        return False
                    # case self.control_channel.INIT:
                    #     pass
                    case self.control_channel.PING:
                        # If packages are pending send them else send nothing
                        if len(clt.pending_packages) > 0:
                            package = clt.pending_packages.pop(0)[1]
                            ses = package[0]['ses']
                            data = package[1]
                        else:
                            data = ""
                        self.send(sock=sock,
                                  ses=ses,
                                  typ=self.control_channel.ANS,
                                  ac=ac,
                                  data=str(data))
                    case self.control_channel.REQ:
                        # Check if target client exists and then create session
                        msg = payload.split(' ')
                        if len(msg) == 2:
                            client_id, password = msg
                            target = self.client_storage.get_client(client_id)
                            try:
                                if target:
                                    # Create session and send the id to the client else send ''
                                    # raises OverflowError: No session left for client

                                    timeout = False

                                    def start_timeout():
                                        nonlocal timeout
                                        timeout = True

                                    # Start timeout
                                    timer = threading.Timer(self.udp_wait_timeout, start_timeout)
                                    self.timers.append(timer)
                                    timer.start()

                                    # As long as no timeout -> wait for answer
                                    while not timeout:
                                        # If already in cache return
                                        self.udp_receive_event.wait(self.udp_wait_timeout)
                                        ip = self.udp_received.get(password, None)
                                        if ip and ip[0] == clt.socket.getpeername()[0]:
                                            logging.getLogger('yard_server.udp').info(
                                                f"Received corresponding UDP message from {ip[0]}")
                                            timer.cancel()
                                            self.udp_receive_event.clear()
                                            session_id = self.client_storage.create_session(clt, target)
                                            logging.getLogger('yard_server.session').info(
                                                f"Create Session {session_id} ({clt}, {target})")
                                            self.send(sock=sock,
                                                      typ=self.control_channel.ANS,
                                                      ac=ac,
                                                      data=f"{session_id} {ip[0]} {ip[1]}")
                                            break
                                else:
                                    self.send(sock=sock,
                                              typ=self.control_channel.ANS,
                                              ac=ac,
                                              data='')
                            except OverflowError:
                                logging.getLogger('yard_server.session').error(
                                    f"No session left for client {clt.client_id} and {target.client_id}")
                                self.send(sock=sock,
                                          typ=self.control_channel.ERR,
                                          ac=ac,
                                          data="No session left for you and your target")
                            except Exception as e:
                                logging.getLogger('yard_server.session').error(e.__str__())
                        else:
                            logging.getLogger('yard_server.session').error(
                                f"Not enough parameters received")
                            self.send(sock=sock,
                                      typ=self.control_channel.ERR,
                                      ac=ac,
                                      data="Wrong number of parameters")
                    case self.control_channel.CONN:
                        # Get target and add it to pending packages
                        target_client = clt.get_partner_of_session(ses)
                        if target_client:
                            if target_client.socket:
                                # raises OverflowError
                                package = [
                                    self.control_channel.create_header(ses, self.control_channel.ANS, pl=payload),
                                    payload
                                ]
                                target_client.pending_packages.append((ses, package))
                                self.send(sock=sock,
                                          typ=self.control_channel.ANS,
                                          ac=ac)
                            else:
                                self.send(sock=sock,
                                          typ=self.control_channel.WARN,
                                          ac=ac,
                                          data="Target is not online")
                        else:
                            self.send(sock=sock,
                                      typ=self.control_channel.WARN,
                                      ac=ac,
                                      data="Session does not exists")
                    case self.control_channel.TERM:
                        # Terminate session if it exists
                        if clt.delete_session(ses):
                            self.send(sock=sock,
                                      typ=self.control_channel.ANS,
                                      ac=ac)
                        else:
                            self.send(sock=sock,
                                      typ=self.control_channel.ERR,
                                      ac=ac,
                                      data="Session does not exists")
                    case self.control_channel.REN:
                        # Renew everything based on the provided fingerprint
                        try:
                            old = self.client_storage.get_client_by_fingerprint(uuid.UUID(payload))
                            old.set_offline(leave_sock=True)
                            self.client_storage.pop_client(old.client_id)
                            new = self.client_storage.create_client(fingerprint=old.fingerprint,
                                                                    sock=sock)
                            logging.getLogger('yard_server.connection').info(
                                f"Renewed ID for {new.fingerprint} ({old.client_id} to {new.client_id})")
                            self.send(sock=sock,
                                      typ=self.control_channel.ANS,
                                      ac=ac,
                                      data=f"{new.client_id} {sock.getpeername()[0]}")
                        except ValueError as e:
                            # raises ValueError: If you pass the wrong format of fingerprint
                            try:
                                self.send(sock=sock,
                                          typ=self.control_channel.ERR,
                                          ac=ac,
                                          data=f"UUID is not in correct format")
                            finally:
                                logging.getLogger('yard_server.connection').error(e)
                                return False
                    # case self.control_channel.ANS:
                    #     pass
                    # case self.control_channel.ERR:
                    #     pass
                    # case self.control_channel.WARN:
                    #     pass
                    case _:
                        # If it is an unknown or not supported message type
                        try:
                            self.send(sock=sock,
                                      typ=self.control_channel.ERR,
                                      ac=ac,
                                      data="Unknown message type")
                        finally:
                            return False
            else:
                try:
                    self.send(sock=sock,
                              typ=self.control_channel.ERR,
                              ac=ac,
                              data="Client is not initialized")
                finally:
                    logging.getLogger('yard_server.connection').warning(f"Client is not initialized")
                    return False
            return True
        except OverflowError as e:
            # raises OverflowError: When Parameters could not be converted to their byte-representation
            # and are therefore to long for the header
            try:
                self.send(sock=sock,
                          typ=self.control_channel.ERR,
                          ac=ac,
                          data=f"Unexpected server error please contact the developers: code 1000")
            finally:
                logging.getLogger('yard_server.connection').exception(e)
                return False
        except Exception as e:
            try:
                self.send(sock=sock,
                          typ=self.control_channel.ERR,
                          ac=ac,
                          data="Unexpected server error please contact the developers: code 1")
            finally:
                logging.getLogger('yard_server.connection').exception(e)
                return False

    def handle_client(self, connection: 'socket.socket', address: Tuple[str, Union[str, int]]) -> None:
        """
        Handle the client.
        Evaluate the action based on receiving messages.

        :param connection: socket.socket: The socket of the connection
        :param address: Tuple[address, port]
        :return: None
        """

        connection_logger = logging.getLogger('yard_server.connection')
        self.connections.append(connection)
        try:
            connection_logger.info("Accepting {}:{}".format(*address))
            while not self.stopping:
                package = self.control_channel.receive(connection)
                connection_logger.info(  # TODO: Change to debug in production
                    "Received data from {}:{} || Header: {} || Payload: {}".format(*address, *package))
                connection_logger.debug("Answer to {}:{}".format(*address))
                # If answer_message returns false close connection
                if not self.answer_message(connection, package):
                    break
        except ConnectionAbortedError as e:
            # When there is a problem with the header, the connection is treated as aborted
            connection_logger.warning(e)
        except Exception as e:
            # Catch all unexpected Exceptions
            connection_logger.exception(e)
        finally:
            logging.getLogger('yard_server.connection').info("Closing connection {}:{}".format(*address))

            # Close connection and set client offline
            cl = self.client_storage.get_client_by_socket(connection)
            if cl:
                cl.set_offline()
            connection.close()

    def server_loop(self) -> None:
        """
        Starts the main server loop.
        Waits for a new connection and then starts a new thread to handle the client.

        :return: None
        """
        main_logger = logging.getLogger('yard_server.main')
        try:
            while not self.stopping:
                main_logger.info("Control server is waiting for connections")
                connection, address = self.control_server.accept()

                # Start new thread and handle client
                thread = threading.Thread(target=self.handle_client, args=(connection, address))
                main_logger.debug("Control server starts new thread")
                thread.start()
        except Exception as e:
            main_logger.exception(e)
            self.stop()

    def server_udp_loop(self) -> None:
        """
        Starts the main server udp loop.
        Waits for a new connection and then starts a new thread to handle the udp client.
        :return: None
        """
        main_logger = logging.getLogger('yard_server.main')

        def clear(password):
            nonlocal main_logger
            event = threading.Event()

            def start_event():
                nonlocal event
                event.set()

            # Start timeout
            timer = threading.Timer(self.udp_save_timeout, start_event)
            self.timers.append(timer)
            timer.start()

            event.wait()
            self.udp_received.pop(password)
            main_logger.debug("Pop UDP receive message")
            if not self.udp_received:
                self.udp_receive_event.clear()
                main_logger.debug("Clear UDP receive event")

        try:
            while not self.stopping:
                main_logger.info("Waiting for UDP connections")
                data, address = self.transmission_channel.receive_raw(self.transmission_server)
                data = str(data, self.transmission_channel.encoding)
                main_logger.info(f"Received UDP data from {address} || Data: {data}")
                if not self.udp_received.get(data, None):
                    self.udp_receive_event.set()
                    self.udp_received[data] = address
                    thread = threading.Thread(target=clear, args=[data])
                    thread.start()
        except Exception as e:
            main_logger.exception(e)
            self.stop()

    def test_event(self):
        while not self.stopping:
            self.udp_receive_event.wait()
            print(self.udp_received['data'])
            self.udp_receive_event.clear()

    def start(self) -> None:
        """
        Start the yard-Server.

        :return: None
        """
        start_logger = logging.getLogger('yard_server.starting')
        start_logger.info("Control server is starting")

        self.control_server.listen()
        start_logger.info("Control server is now listening")

        start_logger.debug("Control server starts new thread")
        thread = threading.Thread(target=self.server_loop)
        thread.start()

        start_logger = logging.getLogger('yard_server.starting')
        start_logger.info("Transmission server is starting")

        start_logger.debug("Transmission server starts new thread")
        thread = threading.Thread(target=self.server_udp_loop)
        thread.start()

    def stop(self):
        stop_logger = logging.getLogger('yard_server.client')
        stop_logger.info("Control server is now stopping")
        stop_logger.debug("Closing connections")
        for i in self.connections:
            i.close()
        stop_logger.debug("Stop timers")
        for i in self.timers:
            i.cancel()
        stop_logger.debug("Stop endless loops")
        self.stopping = True
        self.control_server.close()
