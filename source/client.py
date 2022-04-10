import logging

from objects import yardlogging
from objects.clientdaemon import ClientDaemon

yardlogging.setup_client()


class ClientCLI:
    clt = None

    def __init__(self, clt: ClientDaemon):
        self.clt = clt

    def start_client(self):
        self.clt.connect()
        self.clt.start()

    def input_loop(self):
        cmd_logger = logging.getLogger('yard_client.cmd')
        while True:
            try:
                command = input('>>> ')
                match command.split():
                    case [action, *params]:
                        match action:
                            case 'exit':
                                try:
                                    self.clt.close()
                                finally:
                                    break
                            case 'start':
                                self.start_client()
                            case 'help':
                                print("YARD - Yet Another Remote Desktop")
                                print("\nstart - connect to server(address in settings/conf.json) and get ID")
                                print("\nconnect ID - connect to client and start Remote Desktop Transmission")
                                print("\nreset - Reset connection")
                                print("\nexit - Close Program")
                            case 'connect':
                                if len(params) == 1:
                                    self.clt.connect_to_client(params[0])
                                else:
                                    cmd_logger.warning(f"Connect needs only 1 parameter, {len(params)} were given")
                            case 'reset':
                                self.clt.reset()
                            case _:
                                cmd_logger.warning("Unknown command. Enter help to get help")
                    case _:
                        cmd_logger.warning("Unknown structure. Enter help to get help")
            except Exception as ex:
                cmd_logger.exception(ex)


client = ClientDaemon()
client_cli = ClientCLI(client)
try:
    client_cli.input_loop()
except Exception as e:
    logging.getLogger('yard_client').exception(e)
    client.close()
