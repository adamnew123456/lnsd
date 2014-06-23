#!/usr/bin/env python3
"""
This is an implementation of the LAN naming service, as defined in the given 
README.

This particular daemon is capable of:

 - Implementing the definition of LNS.
 - Reading configuration values from an INI-style file or from the command line.
 - Allowing clients to query the host-name mapping via DBus.
"""

import configparser
import getopt
import socket
import sys
import threading

from lns.bidict import *
from lns import daemon, proto, service
from lns.socks import session

PID_FILE = '/tmp/lnsd.pid'
LOG = '/tmp/lnsd.log'
class LNS_Daemon(daemon.Daemon):
    def dbus_service(self, lnsd):
        """
        Launches the DBus service.
        """
        service.run_service(lnsd)

    def proxy_thread(self, lnsd):
        """
        Launches the SOCKS proxy.
        """
        proxy = session.SessionManager(lnsd, 1080)
        proxy.run()

    def run(self, lnsd):
        """
        Launches the DBus handling thread, the proxy thread, and well as the LNS protocol handler.
        """
        dbus_thread = threading.Thread(target=self.dbus_service, args=(lnsd,), daemon=True)
        dbus_thread.start()

        proxy_thread = threading.Thread(target=self.proxy_thread, args=(lnsd,), daemon=True)
        proxy_thread.start()

        proto.protocol_handler(lnsd)

class LNS:
    """
    A container, meant to make it easy for the LNS protocol handler and the DBus
    service to share data.
    """
    def __init__(self, port, timeout, heartbeat, name, daemonize):
        self.port = port
        self.timeout = timeout
        self.heartbeat = heartbeat
        self.name = name
        self.should_daemonize = daemonize

        # Note that this lock is only used by the protocol handler when it modifies
        # this dict - this is because the DBus service is guaranteed to never touch
        # this dict, only read from it.
        self.host_names_lock = threading.Lock()
        self.host_names = bidict()

        self.quit_event = threading.Event()

    def main(self):
        """
        Starts both the DBus service as well as the protocol, daemonizing before
        hand if necessary.
        """
        daemon = LNS_Daemon(PID_FILE, stdout=LOG, stderr=None, home_dir='/')
        if self.should_daemonize:
            daemon.start(self)
        else:
            # (This bypasses the daemon setup)
            daemon.run(self)

##### BELOW HERE LIES THE ARGUMENT PARSING AND CONFIGURATION ROUTINES #####

HELP = """lnsd - An implementation of the LAN Naming Service protocol.
Usage:

    lnsd [-c config] [-p port] [-h heartbeat] [-t timeout] [-n name]

Options:

    -c CONFIG       Config is the name of an INI-style configuration 
                    file to load configuration values from. Note that
                    any options provided on the command line override the
                    contents of the configuration file. By default, the 
                    configuration file is located at '/etc/lnsd.conf'

    -p PORT         The port to bind to, 15051 by default.

    -t TIMEOUT      How many seconds to wait for an ANNOUNCE message before
                    declaring a host dead. By default, the timeout is 30 seconds.

    -a HEARTBEAT    How often, in seconds, to send an ANNOUNCE message to peers.
                    By default, the interval is 10 seconds.

    -n NAME         The name that lnsd will try to assign to this machine. The 
                    default is the system's hostname.

    -D              This causes lnsd to go into daemon mode. By default, lnsd
                    remains in the foreground.

    -h              Print out this help message.
""".strip()

MAX_PORT = 2 << 15 - 1

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
        print('Invalid port number:', argvalue)
        sys.exit(1)

def check_timeout_or_die(argvalue):
    """
    Ensures that the argument value is a valid timeout value, or dies.

     - The timeout must be a valid integer.
     - The timeout must be > 0.
    """
    try:
        timeout = int(argvalue)
        if timeout < 0:
            raise ValueError
        return timeout
    except ValueError:
        print('Invalid timeout value:', argvalue)
        sys.exit(1)

def check_heartbeat_or_die(argvalue):
    """
    Ensures that an argument is a valid heartbeat interval, or dies.

     - The interval must be a valid integer.
     - The interval must be > 0.
    """
    try:
        interval = int(argvalue)
        if interval < 0:
            raise ValueError
        return interval
    except ValueError:
        print('Invalid heartbeat interval:', argvalue)
        sys.exit(1)

def check_name_or_die(argvalue):
    """
    Ensures that the argument value is a valid host name, or dies.

     - The host name must be valid ASCII.
     - The host name must not contain unprintable characters.
     - The length of the host name must be in the range [1, MSG_SIZE].
    """
    try:
        name = bytes(argvalue, 'ascii')

        # The reason that MSG_SIZE - 1is used here is because the spec states that the
        # maximum data size is MSG_SIZE, and the type field of the message uses up
        # one byte.
        if not name  or len(name) > proto.MSG_SIZE - 1:
            raise ValueError

        for ascii_code in name:
            if ascii_code <= 32 or ascii_code == 127:
                raise ValueError

        return name
    except ValueError:
        print("Host name cannot be empty or contain nonprintable characters")
        sys.exit(1)
    except UnicodeEncodeError:
        print("Host name must be valid ASCII")
        sys.exit(1)

# This is how values are organized in the 'configuration lists' below
DEFAULT, CONFIGFILE, CMDLINE = range(3)
def collapse_value(param):
    """
    Collapses a parameter into a single value - the last non-None value.
    For example:

    >>> x = [None, None, None]
    >>> x[DEFAULT] = 'foo'
    >>> x[CONFIGFILE] = 'bar'
    >>> collapse_value(x)
    bar
    """
    valid_values = [value for value in param if value is not None]
    return valid_values[-1]

def main():
    if '-h' in sys.argv[1:]:
        print(HELP)
        sys.exit(1)

    opts, args = getopt.getopt(sys.argv[1:], 'c:p:t:a:n:D')

    config_file = '/etc/lnsd.conf'
    port = [15051, None, None]
    timeout = [30, None, None]
    heartbeat = [10, None, None]
    name = [bytes(socket.gethostname(), 'ascii'), None, None]
    daemonize = [False, None, None]

    # No non-named arguments are taken.
    if args:
        print(HELP)
        sys.exit(1)

    for optname, optvalue in opts:
        if optname == '-c':
            config_file = optvalue
        elif optname == '-p':
            port[CMDLINE] = check_port_or_die(optvalue)
        elif optname == '-t':
            timeout[CMDLINE] = check_timeout_or_die(optvalue)
        elif optname == '-a':
            heartbeat[CMDLINE] = check_heartbeat_or_die(optvalue)
        elif optname == '-n':
            name[CMDLINE] = check_name_or_die(optvalue)
        elif optname == '-D':
            daemonize[CMDLINE] = True
        else:
            print(HELP)
            sys.exit(1)

    config = configparser.ConfigParser()
    config.read(config_file)
    if 'lnsd' in config:
        for key, value in config['lnsd'].items():
            if key == 'port':
                port[CONFIGFILE] = check_port_or_die(value)
            elif key == 'timeout':
                timeout[CONFIGFILE] = check_timeout_or_die(value)
            elif key == 'heartbeat':
                heartbeat[CONFIGFILE] = check_heartbeat_or_die(value)
            elif key == 'hostname':
                name[CONFIGFILE] = check_name_or_die(value)
            elif key == 'daemonize':
                value = value.lower()
                if value == 'true':
                    daemonize[CONFIGFILE] = True
                elif value == 'false':
                    daemonize[CONFIGFILE] = False
                else:
                    print('daemon option in the config file'
                            ' must be either "true" or "false"')
                    sys.exit(1)
            else:
                print('Excess configuration option: "{}" = "{}"'.format(
                            key, value))
                sys.exit(1)

    # Figure out the highest priority values for each of the parameters.
    port = collapse_value(port)
    timeout = collapse_value(timeout)
    heartbeat = collapse_value(heartbeat)
    name = collapse_value(name)
    daemonize = collapse_value(daemonize)

    LNS(port, timeout, heartbeat, name, daemonize).main()

if __name__ == '__main__':
    main()
