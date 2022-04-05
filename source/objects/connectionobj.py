import uuid
from typing import Optional

from protocol.yardtransmission import YardTransmission


class ConnectionObj:
    client_id: str = None
    fingerprint: Optional[uuid.UUID] = None
    session_id: int = None
    online: bool = None
    transmission: Optional[YardTransmission] = None

    def __init__(self,
                 client_id: str,
                 session_id: int,
                 fingerprint: Optional[uuid.UUID] = None,
                 online: bool = False,
                 transmission: Optional[YardTransmission] = None):
        if not fingerprint or fingerprint.version == 4:
            self.client_id = client_id
            self.fingerprint = fingerprint
            self.session_id = session_id
            self.online = online
            self.transmission = transmission
        else:
            raise ValueError('Connection fingerprint is not version 4')

    def __str__(self):
        return str({'client_id': str(self.client_id),
                    'fingerprint': str(self.fingerprint),
                    'session_id': str(self.session_id),
                    'online': str(self.online),
                    'transmission': str(self.transmission)})
