"""
Yard logging module.

Module for all you yardy logging needs.
You need to call setup_server() or setup_client() to use this module.

Example:
    import yardlogging
    import logging

    setup_server()
    logger.getLogger('yard_server').error("This is an error")
"""

import logging


# 2021-12-30 15:51:26,492 [yardserver.init] [CLIENTOBJ:23] [DEBUG] === Initializing server
file_formatter = logging.Formatter('%(asctime)s [%(name)s] [%(module)s:%(lineno)d] [%(levelname)s] === %(message)s')
# [yardclient.init] [DEBUG] === Initializing client
console_formatter = logging.Formatter('[%(name)s] [%(levelname)s] === %(message)s')


def setup_server() -> None:
    """
    Setup logging for a server

    Use logging.getLogger('yard_server') to access the logging
    :return: None
    """
    server_logger = logging.getLogger('yard_server')
    server_logger.setLevel(logging.DEBUG)

    log_file = logging.FileHandler(filename='data/server.log')
    log_file.setLevel(logging.DEBUG)
    log_file.setFormatter(file_formatter)

    log_console = logging.StreamHandler()
    log_console.setLevel(logging.INFO)
    log_console.setFormatter(console_formatter)

    server_logger.addHandler(log_file)
    server_logger.addHandler(log_console)


def setup_client():
    """
    Setup logging for a client

    Use logging.getLogger('yard_client') to access the logging
    :return: None
    """
    client_logger = logging.getLogger('yard_client')
    client_logger.setLevel(logging.DEBUG)

    log_file = logging.FileHandler(filename='data/client.log')
    log_file.setLevel(logging.DEBUG)
    log_file.setFormatter(file_formatter)

    log_console = logging.StreamHandler()
    log_console.setLevel(logging.INFO)
    log_console.setFormatter(console_formatter)

    client_logger.addHandler(log_file)
    client_logger.addHandler(log_console)
