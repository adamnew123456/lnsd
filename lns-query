#!/usr/bin/env python3
"""
Queries an LNS service running over DBus.
"""

import dbus
import getopt
import sys

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

    bus = dbus.SessionBus()
    obj = bus.get_object('org.adamnew123456.lnsd', '/org/adamnew123456/lnsd')
    iface = dbus.Interface(obj, 'org.adamnew123456.lnsd')

    if mode == ALL:
        for host, name in iface.QueryAll().items():
            print(host,name)
    elif mode == HOST:
        print(iface.QueryHost(option))
    elif mode == NAME:
        print(iface.QueryName(option))
    elif mode == QUIT:
        iface.Quit()

if __name__ == '__main__':
    main()
