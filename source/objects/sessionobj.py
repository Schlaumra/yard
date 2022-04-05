from typing import Tuple

from objects.clientobj import ClientObj


class SessionObj:
    """
    An object-class for saving information about a session.

    :param session_id: int:
    :param connection: tuple['Clientobj', 'Clientobj']
    """
    session_id: int = None
    connection: Tuple['ClientObj', 'ClientObj'] = None

    def __init__(self, session_id: int, connection: Tuple['ClientObj', 'ClientObj']):
        self.session_id = session_id
        self.connection = connection

    def __str__(self):
        return str({'session_id': self.session_id, 'connection': self.connection})

    def get_partner(self, own_id: str) -> ClientObj:
        """
        Get partner of session based on own client_id.

        :param own_id: str: The id of the client
        :return: ClientObj: The partner client
        """
        for client in self.connection:
            if client.client_id != own_id:
                return client
