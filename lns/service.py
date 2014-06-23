"""
A service which listens for control commands over IP sockets.
"""

import socket

from lns import query_proto

SERVICE_PORT = 10771

def run_service(lnsd):
    """
    Handles connections on the manager socket.
    """
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind(('localhost', SERVICE_PORT))
    except OSError:
        print('Cannot acquire command port {} - dying'.format(SERVICE_PORT))
        lnsd.quit_event.set()
        return

    server.listen(5)
    while True:
        client, _ = server.accept()
        message = query_proto.recv_message(client)

        if isinstance(message, query_proto.Name):
            name = bytes(message.hostname, 'ascii')
            with lnsd.host_names_lock:
                ip = (~lnsd.host_names).get(name, None)
            query_proto.send_message(client, query_proto.IP(ip))
        elif isinstance(message, query_proto.IP):
            with lnsd.host_names_lock:
                name = lnsd.host_names.get(message.ip, None)
            if isinstance(name, bytes):
                name = str(name, 'ascii')
            query_proto.send_message(client, query_proto.Name(name))
        elif isinstance(message, query_proto.GetAll):
            host_ip_dict = {}
            with lnsd.host_names_lock:
                for host, ip in (~lnsd.host_names).items():
                    host_ip_dict[str(host, 'ascii')] = ip
                        
            query_proto.send_message(client, query_proto.NameIPMapping(host_ip_dict))
        elif isinstance(message, query_proto.Quit):
            lnsd.quit_event.set()
            break

    server.close()
