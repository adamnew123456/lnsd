#!/usr/bin/env python3
"""
The query program for lnsd, which can connect to the daemon to query the
name-host mapping.
"""
import getopt
import sys

from lns_ng import control_proto, net_proto

HELP = """lns-query - Query the lnsd server.
Usage:

    lns-query [-h] <-a | -i ip | -n hostname | -q> [-p control_port]

Options:

    -a
        Outputs a list of all IP-hostname pairs, with the IP listed first
        and the hostname listed second. E.g.

            1.2.3.4 A
            5.6.7.8 B
            9.10.11.12 C

    -i IP
        Prints out the hostname associated with the given IP address;
        produces no output if no hostname is found.

    -n HOSTNAME
        Prints out the IP addresses associated with the given hostname;
        produces no output if no IP addresses are found.

    -p CONTROL_PORT
        The port to use to connect to the server (default: 10771).

    -q
        Terminates the server.

    -h
        Prints out this help page.
"""

USAGE = "lns-query [-h] <-a | -i IP | -n hostname | -q> [-p control_port]"

MAX_PORT = 65535
def check_port_or_die(argvalue):
    """
    Ensures that the argument value is a valid port number, or dies.

     - The port must be a valid integer.
     - The port must be in the range [1, MAX_PORT]
    """
    try:
        port = int(argvalue)
        if port < 1 or port > MAX_PORT:
            raise ValueError

        return port
    except ValueError:
        print('Invalid port number:', argvalue, file=sys.stderr)
        sys.exit(1)

def check_name_or_die(argvalue):
    """
    Ensures that the argument value is a valid host name, or dies.

     - The host name must be valid ASCII.
     - The host name must not contain unprintable characters.
     - The length of the host name must be in the range [1, MSG_SIZE].
    """
    try:
        net_proto.verify_hostname(argvalue.encode('ascii'))
        return argvalue
    except ValueError as err:
        print('Invalid hostname: ' + str(err), file=sys.stderr)
        sys.exit(1)

def check_ip_or_die(argvalue):
    """
    Ensures that the argument value is a valid IPv4 address, or dies.
    """
    try:
        control_proto.verify_ipv4_address(argvalue)
        return argvalue
    except ValueError as err:
        print('Invalid IP address: ' + str(err), file=sys.stderr)
        sys.exit(1)

def get_ip_addresses(host, client):
    """
    Prints out the IP addresses associated with the given hostname, or none
    if no IP addresses exist.
    """
    check_name_or_die(host)
    for ip in client.get_ip(host):
        print(ip)

def get_hostname(ip, client):
    """
    Prints out the hostname associated with the given IP address, or nothing
    if no hostname exists.
    """
    check_ip_or_die(ip)
    host = client.get_host(ip)
    if host is not None:
        print(host)

def get_all(client):
    """
    Prints out each IP address and its associated hostname, or nothing if no
    hosts are known to the server.
    """
    host_ip_map = client.get_host_ip_mapping()
    for host, addrs in host_ip_map.items():
        for addr in addrs:
            print(addr, host)

def terminate(client):
    """
    Terminates the server.
    """
    client.terminate()

def main():
    if '-h' in sys.argv[1:]:
        print(HELP)
        return 0

    try:
        opts, rest = getopt.getopt(sys.argv[1:], 'ai:n:p:q')
    except getopt.GetoptError as err:
        print(err, file=sys.stderr)
        return 1

    if rest:
        print('No positional argumetns allowed', file=sys.stderr)

    # The mode stores both the callable, as well as the arguments to pass
    # to it (excepting the ClientHandler, which is done automatically)
    mode = None
    control_port = control_proto.CONTROL_PORT
    for optname, optvalue in opts:
        if optname == '-a':
            mode = (get_all, [])
        elif optname == '-i':
            mode = (get_hostname, [optvalue])
        elif optname == '-n':
            mode = (get_ip_addresses, [optvalue])
        elif optname == '-q':
            mode = (terminate, [])
        elif optname == '-p':
            control_port = check_port_or_die(optvalue)

    if mode is None:
        print('One option out of -a, -i, -n, -q is required',
            file=sys.stderr)
        return 1

    client = control_proto.ClientHandler(control_port)
    with client:
        func, args = mode
        args.append(client)
        func(*args)
    return 0
