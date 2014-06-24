#!/usr/bin/env python3
"""
Queries an LNS service for hostname and IP information. Can also terminate the
LNS service.
"""

import getopt
import socket
import sys

from lns import query_proto, service

HELP = """lns-query - Accesses the host-name mapping provided by lnsd.
Usage:

    lns-query <-a | -i host | -n name | -q>

Options:

    -a          Gets a list of all host-name pairs.
    -i HOST     Gets the name associated with the given IP address.
    -n NAME     Gets the IP address associated with the given name.
    -q          Terminates the server.
""".strip()

def main():
    if '-h' in sys.argv[1:]:
        print(HELP)
        sys.exit(1)

    opts, args = getopt.getopt(sys.argv[1:], 'ai:n:q')

    ALL, HOST, NAME, QUIT = range(4)
    option = None
    mode = None

    for optname, optvalue in opts:
        if optname == '-a':
            if mode is not None:
                print('Multiple queries not allowed')
                sys.exit(1)
            mode = ALL
        elif optname == '-i':
            if mode is not None:
                print('Multiple queries not allowed')
            mode = HOST
            option = optvalue
        elif optname == '-n':
            if mode is not None:
                print('Multiple queries not allowed')
            mode = NAME
            option = optvalue
        elif optname == '-q':
            mode = QUIT

    if mode is None:
        print(HELP)
        sys.exit(1)

    sock = socket.socket()
    try:
        sock.connect(('localhost', service.SERVICE_PORT))
    except OSError:
        print('Service is not running')
        sys.exit(1)

    def return_status_code(code):
        sock.close()
        sys.exit(code)

    if mode == ALL:
        query_proto.send_message(sock, query_proto.GetAll())
        result = query_proto.recv_message(sock)
        assert isinstance(result, query_proto.NameIPMapping)
        for name, ip in result.name_ips.items():
            print(ip, name)
        return_status_code(0)
    elif mode == HOST:
        query_proto.send_message(sock, query_proto.IP(option))
        result = query_proto.recv_message(sock)
        assert isinstance(result, query_proto.Name)
        if result.hostname is not None:
            print(result.hostname)
            return_status_code(0)
        else:
            return_status_code(1)
    elif mode == NAME:
        query_proto.send_message(sock, query_proto.Name(option))
        result = query_proto.recv_message(sock)
        assert isinstance(result, query_proto.IP)
        if result.ip is not None:
            print(result.ip)
            return_status_code(0)
        else:
            return_status_code(1)
    elif mode == QUIT:
        query_proto.send_message(sock, query_proto.Quit())
        return_status_code(0)

    sock.close()

if __name__ == '__main__':
    main()
