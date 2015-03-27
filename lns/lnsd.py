#!/usr/bin/env python3
"""
The daemon runner for lnsd, which handles both configuration options as well
as command line options.
"""
import configparser
import getopt
import logging
import socket
import sys

from lns import daemon, control_proto, net_proto, reactor, utils

class LNSDaemon(daemon.Daemon):
    def run(self, hostname, control_port, network_port):
        my_reactor = reactor.Reactor()
        net_handler = net_proto.ProtocolHandler(my_reactor, hostname,
            port=network_port)
        control_handler = control_proto.ProtocolHandler(net_handler,
            my_reactor, port=control_port)

        net_handler.open()
        control_handler.open()
        while control_handler.is_running():
            my_reactor.poll(net_handler.get_time_until_next_announce())

        net_handler.close()
        control_handler.close()

HELP = """lnsd - An implementation of the LAN Naming Service protocol.
Usage:

    lnsd [-c config] [-p [control-port]:[network-port]] [-n name] [-v]

Options:

    -c CONFIG
        Config is the name of an INI-style configuration file to load
        configuration values from. Note that any options provided on the
        command line override the contents of the configuration file. By
        default, no configuration file is processed.

    -p [CONTROL_PORT]:[NETWORK_PORT]
        The external port (default: 15051) and internal port (default: 10771)
        to bind to. The external port is opened up to receive Announce
        messages from remote machines, while the internal port is used for
        control messages to the server.

    -n NAME
        The name that lnsd will try to assign to this machine. The default is
        the system's hostname.

    -D
        This causes lnsd to go into daemon mode. By default, lnsd remains in
        the foreground.

    -v
        Print out logging messages.

    -h
        Print out this help message.
"""

USAGE = 'lnsd [-c config] [-p [control-port]:[network-port]] [-n name] [-v]'

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

def check_boolean_or_die(argvalue):
    """
    Ensures that the argument value is a valid boolean, which means that
    its lowercase form must be either 'true' or 'false'
    """
    bool_map = {'true': True, 'false': False}
    try:
        return bool_map[argvalue.lower()]
    except KeyError:
        print('Invalid boolean:', argvalue)
        sys.exit(1)

class ConfigHandler:
    """
    Processes command line arguments, as well as the configuration file, and
    gets the highest priority values for lnsd's options.
    """
    PRI_DEFAULT, PRI_CONFIG, PRI_CMDLINE = range(3)

    def __init__(self):
        self.net_port = (self.PRI_DEFAULT, net_proto.NET_PORT)
        self.control_port = (self.PRI_DEFAULT, control_proto.CONTROL_PORT)
        self.name = (self.PRI_DEFAULT, socket.gethostname())
        self.daemonize = (self.PRI_DEFAULT, False)
        self.verbose = (self.PRI_DEFAULT, False)

    def get_network_port(self):
        return self.net_port[1]

    def get_control_port(self):
        return self.control_port[1]

    def get_name(self):
        return self.name[1]

    def get_daemonize(self):
        return self.daemonize[1]

    def get_verbose(self):
        return self.verbose[1]

    def assign(self, option, priority, value):
        """
        Assigns the given value to the given option, only if the priority for
        the new value is higher than that of the old value.
        """
        old_pri, _ = getattr(self, option)
        if old_pri > priority:
            return

        setattr(self, option, (priority, value))

    def process_commandline_args(self, argv):
        """
        Processes command line arguments, and stores the options specified by
        those arguments.
        """
        opts, rest = getopt.getopt(argv, 'c:p:n:Dv')
        if rest:
            # We have to hijack getopt's exception value since that's what the
            # caller should already be watching
            raise getopt.GetoptError('No positional arguments allowed')

        for optname, optvalue in opts:
            if optname == '-c':
                self.process_config_file(optvalue)
            elif optname == '-p':
                try:
                    control_port, net_port = optvalue.split(':')
                except ValueError:
                    print('-p option must contain two ports '
                        '(or an empty string) joined by a :', file=sys.stderr)

                if control_port:
                    port = check_port_or_die(control_port)
                    self.assign('control_port', self.PRI_CMDLINE, port)
                if net_port:
                    port = check_port_or_die(net_port)
                    self.assign('net_port', self.PRI_CMDLINE, port)
            elif optname == '-n':
                hostname = check_name_or_die(optvalue)
                self.assign('name', self.PRI_CONFIG, hostname)
            elif optname == '-D':
                self.assign('daemonize', self.PRI_CMDLINE, True)
            elif optname == '-v':
                self.assign('verbose', self.PRI_CMDLINE, True)

    def process_config_file(self, filename):
        """
        Processes the configuration file, storing the options contained within
        it.
        """
        config = configparser.ConfigParser()
        config.read(filename)
        if 'lnsd' in config:
            lnsd_config = config['lnsd']
            if 'net_port' in lnsd_config:
                port = check_port_or_die(lnsd_config['net_port'])
                self.assign('net_port', self.PRI_CONFIG, port)
            elif 'control_port' in lnsd_config:
                port = check_port_or_die(lnsd_config['control_port'])
                self.assign('control_port', self.PRI_CONFIG, port)
            elif 'hostname' in lnsd_config:
                hostname = check_name_or_die(lnsd_config['hostname'])
                self.assign('name', self.PRI_CONFIG, hostname)
            elif 'daemonize' in lnsd_config:
                is_daemon = check_boolean_or_die(lnsd_config['daemonize'])
                self.assign('daemonize', self.PRI_CONFIG, is_daemon)
            elif 'verbose' in lnsd_config:
                is_verbose = check_boolean_or_die(lnsd_config['verbose'])
                self.assign('verbose', self.PRI_CONFIG, is_verbose)

def main():
    if '-h' in sys.argv[1:]:
        print(HELP)
        return 0

    opt_handler = ConfigHandler()
    try:
        opt_handler.process_commandline_args(sys.argv[1:])
    except getopt.GetoptError:
        print(USAGE, file=sys.stderr) 
        return 1

    if opt_handler.get_verbose():
        logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)

    runner = LNSDaemon()
    if opt_handler.get_daemonize():
        runner.start(opt_handler.get_name(), opt_handler.get_control_port(),
            opt_handler.get_network_port())
    else:
        runner.run(opt_handler.get_name(), opt_handler.get_control_port(),
            opt_handler.get_network_port())

if __name__ == '__main__':
    sys.exit(main())
