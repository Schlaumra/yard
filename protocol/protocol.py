import socket
import threading
import uuid


class YardControlChannel:
    version = 0
    header_len = 5
    encoding = "utf-8"

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

    def create_header(self, ses, typ, *args, pl=b"", **kwargs):
        return {'ver': self.version, 'ses': ses, 'typ': typ, 'len': len(pl)}

    def create_byte_header(self, ses, typ, *args, pl=b"", **kwargs):
        header = (self.version.to_bytes(1, 'little')
                  + int(ses).to_bytes(1, 'little')
                  + int(typ).to_bytes(1, 'little')
                  + len(pl).to_bytes(2, 'little'))
        return header

    def send(self, sock, ses, typ, data):
        data = data if type(data) == bytes else bytes(data, self.encoding)
        sock.send(self.create_byte_header(ses, typ, pl=data))
        sock.send(data)

    def receive_header(self, conn):
        msg = {}
        data = conn.recv(self.header_len)
        if data:
            msg['ver'] = data[0]
            msg['ses'] = data[1]
            msg['typ'] = data[2]
            msg['len'] = data[3]
        return msg

    def receive_payload(self, conn, header):
        if header['len'] > 0:
            return conn.recv(header['len']).decode(self.encoding)
        else:
            return ""

    def receive_data(self, conn):
        header = self.receive_header(conn)
        if not header:
            raise Exception # TODO: Create client quited unexpected Exception
        payload = self.receive_payload(conn, header)
        return [header, payload]
