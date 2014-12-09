# Why LNS?

When interacting with other people on a LAN, there is the ever-present problem of
figuring out what another's IP address is. As far as I am aware, there are two 
general solutions, neither of which are fully acceptable:

- Using centralized solutions, like a DNS server, requires a machine to always be
  online. An ideal solution would be distributed, allowing each host to be
  responsible for figuring out which other hosts are on the network.
- Using `/etc/hosts` is unacceptable, since it depends upon each host having a
  static IP address. Under LANs which use DHCP, this is unacceptable.

The LAN Naming System (LNS) was conceived as a solution to both of these problems:

 - LNS is fully decentralized, and each host is responsible for keep a list of
   all other hosts on the network. This allows hosts to drop on and off of the
   network, without having the naming service stop.
 - LNS is capable of handling dynamic IP addresses.

This package has two tools, `lnsd` and `lns-query`.

# Installing The Python Dependencies

`python3 setup.py install` should do the trick. Put the `lnsd` and `lns-query`
programs somewhere in your `$PATH`.

# Using lnsd

`lnsd` is the daemon which manages the LNS protocol on the network. It accepts
the following command line options:

    lnsd - An implementation of the LAN Naming Service protocol.
    Usage:

        lnsd [-c config] [-p [control-port]:[network-port]] [-n name]

    Options:

        -c CONFIG       Config is the name of an INI-style configuration 
                        file to load configuration values from. Note that
                        any options provided on the command line override the
                        contents of the configuration file. By default, the 
                        configuration file is located at '/etc/lnsd.conf'

        -p PORT         The external port (default: 15051) and internal port 
                        (default: 10771) to bind to. The external port is opened
                        up to receive Announce messages from remote machines,
                        while the internal port is used for control messages to
                        the server.

        -n NAME         The name that lnsd will try to assign to this machine. The 
                        default is the system's hostname.

        -D              This causes lnsd to go into daemon mode. By default, lnsd
                        remains in the foreground.

        -h              Print out this help message.

The default configuration file that it reads is `/etc/lnsd.conf`, but can also read
another configuration file provided by the `-c` flag. The configuration file has
the following form:

    [lnsd]
    port=15051
    hostname=foo.example
    daemonize=false

(Note that it accepts any format which Python's configparser module can - for example,
comments).

# Using lns-query

`lns-query` is the query program which connects to the LNS protocol. It accepts
the following command line options:

    lns-query - Accesses the host-name mapping provided by lnsd.
    Usage:

        lns-query <-a | -i host | -n name | -q> [-p control_port]

    Options:

        -a          Gets a list of all host-name pairs.
        -i HOST     Gets the name associated with the given IP address.
        -n NAME     Gets the IP address associated with the given name.
        -p PORT     The port number of the internal control port to connect to
                    (default: 10771).
        -q          Terminates the server.

Consider the following network:

- 192.168.1.1 -> A
- 192.168.1.2 -> B
- 192.168.1.3 -> A

With that network in mind, the following queries will produce the following session:

    $ lns-query -a
    192.168.1.1 A
    192.168.1.2 B
    192.168.1.3 A
    $ lns-query -i 192.168.1.1
    A
    $ lns-query -i 192.168.1.4
    $ lns-query -n A
    192.168.1.1
    192.168.1.3
    $ lns-query -n B
    192.168.1.2
    $ lns-query -n C
    $ lns-query -q  # Terminates the server
