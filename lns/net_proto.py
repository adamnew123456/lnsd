"""
Network Protocol
----------------

This implements the network-facing side of lnsd. There are only two types of
messages, ``ANNOUNCE`` and ``CONFLICT``.

An ``ANNOUNCE`` packet is sent periodically to ensure that a host is still on a
network, and that it is asserting a particular hostname. Other hosts should
record this message as they receive it, to update their caches.
"""
from collections import defaultdict, namedtuple
import logging
import socket
import time

from lns import reactor, utils

LOGGER = logging.getLogger('lns.net_proto')

NET_PORT = 15051

# All packets received from the network are 512 bytes, not including the UDP
# header
PACKET_SIZE = 512

# How often to Announce to the the network, in seconds
ANNOUNCE_ALARM = 10
# How long to wait for another host to Announce before we drop it
ANNOUNCE_TTL = 30

def verify_hostname(hostname_bytes):
    """
    Verifies a hostname, to ensure that it is valid ASCII and that it doesn't
    contain any unprintable characters.

    It returns the encoded version of the hostname if it succeeds, otherwise it
    raises a :class:`ValueError`.
    """
    if not hostname_bytes or len(hostname_bytes) > PACKET_SIZE - 1:
        raise ValueError('Encoded hostname is not between 0 and {} bytes'.
            format(PACKET_SIZE - 1))

    for byte in hostname_bytes:
        if byte < 32 or byte > 126:
            raise ValueError('The character {} is unprintable'.format(
                hex(byte)))
    return hostname_bytes.decode('ascii')

class Announce(namedtuple('Announce', ['hostname'])):
    HEADER = 0x01

    @staticmethod
    def parses(buffer):
        """
        Returns ``True`` if this class can parse the given buffer, or
        ``False`` otherwise.
        """
        return buffer and buffer[0] == Announce.HEADER

    @staticmethod
    def unserialize(buffer):
        """
        Produce a :class:`Announce` message from the contents of a buffer.
        """
        if len(buffer) != PACKET_SIZE:
            raise ValueError('Packet not the correct length - '
                '{} bytes, expected {}'.format(len(buffer, PACKET_SIZE)))

        header, buffer = buffer[0], buffer[1:]
        if header != Announce.HEADER:
            raise ValueError('Header byte incorrect - got {}, expected 0x01'.
                format(hex(header)))

        first_nul = buffer.find(b'\x00')
        if first_nul == -1:
            return Announce(buffer)
        else:
            hostname = buffer[:first_nul]
            return Announce(verify_hostname(hostname))

    def serialize(self):
        """
        Produces a bytestring from this message.
        """
        raw_hostname = self.hostname.encode('ascii')
        if len(raw_hostname) > PACKET_SIZE - 1:
            raise ValueError('Hostname too long - it can be {} bytes at most'.
                format(PACKET_SIZE - 1))

        return b'\x01' + raw_hostname.ljust(PACKET_SIZE - 1, b'\x00')

class ProtocolHandler:
    """
    Handles remote LNS servers, sending out Announce messages and caching them,
    while periodically sending out its own Announce message.
    """
    def __init__(self, a_reactor, hostname, port=NET_PORT):
        self.reactor = a_reactor
        self.port = port
        self.server_sock = None
        self.hostname = hostname

        self.last_announce_time = 0
        self.peer_last_announce_time = {}
        self.host_to_ips = defaultdict(set)
        self.ip_to_host = {}
        self.peer_buffers = defaultdict(bytes)

    def open(self):
        """
        Opens up the network socket for sending and receiving Announce messages.
        """
        LOGGER.debug('Binding to network on port %d', self.port)

        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.server_sock.bind(('0.0.0.0', self.port))
        self.reactor.bind(self.server_sock, reactor.READABLE, self.on_message)
        self.reactor.add_step_callback(self.on_announce_timeout)

        # Go ahead and do our first announce, so that we appear on the
        # network ASAP
        self.on_announce_timeout()

    def close(self):
        """
        Cloes the server socket.
        """
        self.server_sock.close()

    def query_host(self, host):
        """
        Gets a list of IP addresses which have the given hostname.
        """
        return list(self.host_to_ips[host])

    def query_ip(self, ip):
        """
        Gets a host for the given IP address, or None.
        """
        return self.ip_to_host.get(ip, None)

    def get_host_ip_map(self):
        """
        Gets the host to IP address map.
        """
        return {host: list(ips) for host, ips in self.host_to_ips.items() 
            if ips}

    def on_announce_timeout(self):
        """
        This sends out a new announce message, and drops any clients whose last
        announce was too far back in time.
        """
        if time.time() - self.last_announce_time < ANNOUNCE_ALARM:
            # Avoid announcing quickly - since we send out a new Announce()
            # every time the timer runs out, we could receive our own message
            # and send out a new one, causing on_announce_timeout to be called
            # repeatedly as it receives its own messages
            return

        # We want this to happen even if we disconnect, since we don't want to
        # throttle the CPU
        self.last_announce_time = time.time()
        try:
            utils.sendto_all(self.server_sock, Announce(self.hostname).serialize(),
                ('255.255.255.255', self.port))
            LOGGER.debug('Sent an Announce')
        except (OSError, socket.error):
            # At this point, we've disconnected, so we need to sit on the socket
            # until we reconnect; this should be okay, since the socket should
            # still be open (at least it is on Linux).
            #
            # Update 13 December 2014: Cygwin raises a different exception,
            # in the socket module rather than an OSError.
            pass

        now = time.time()
        to_drop = [peer
            for peer, last_announce_time in self.peer_last_announce_time.items()
            if now - last_announce_time > ANNOUNCE_TTL
        ]

        LOGGER.debug('Dropping %d peers', len(to_drop))
        for peer in to_drop:
            LOGGER.debug('-- Dropping: %s', peer)
            del self.peer_last_announce_time[peer]
            del self.peer_buffers[peer]

            peer_name = self.ip_to_host[peer]
            del self.ip_to_host[peer]
            self.host_to_ips[peer_name].remove(peer)

    def get_time_until_next_announce(self):
        """
        Gets the amount of time since the last announce.
        """
        time_since_last_announce = time.time() - self.last_announce_time
        time_until_next_announce = max(ANNOUNCE_ALARM - time_since_last_announce, 0)
        LOGGER.debug('Sending Announce in %f seconds', time_until_next_announce)
        return time_until_next_announce

    def handle_messages(self, host):
        """
        Handles any messages which exist for the given peer.
        """
        buffer_stream = utils.TransactionalBytesIO(self.peer_buffers[host])
        while True:
            with buffer_stream.get_transaction() as txn:
                LOGGER.debug('Message from %s', host)
                stream = txn.get_stream()
                packet = stream.read(PACKET_SIZE)
                if len(packet) < PACKET_SIZE:
                    # We've found the last partial packet, which we want to
                    # keep in the buffer - since we've read it, we have to
                    # abort the transaction to restore its state
                    txn.abort()
                    break
                txn.commit()

                if not Announce.parses(packet):
                    # A corrupt Announce packet (or some other kind of data we
                    # cannot use) is best ignored, since we can't do anything
                    continue

                message = Announce.unserialize(packet)

                self.peer_last_announce_time[host] = time.time()
                # The host might have been renamed, so we have to dispose of
                # the old name before assigning the new one
                if host in self.ip_to_host:
                    old_hostname = self.ip_to_host[host]
                    LOGGER.debug('Host at %s: %s -> %s',
                        host, 
                        old_hostname, 
                        message.hostname)
                    self.host_to_ips[old_hostname].remove(host)

                LOGGER.debug('%s -> %s', host, message.hostname)
                self.ip_to_host[host] = message.hostname
                self.host_to_ips[message.hostname].add(host)

        self.peer_buffers[host] = buffer_stream.read()

    def on_message(self, _):
        """
        Retrieves data from the server socket, and saves it into the peer's
        buffer, possibly handling any complete messages in that peer's
        buffer.
        """
        data, (host, _) = self.server_sock.recvfrom(PACKET_SIZE)
        LOGGER.debug('%d bytes of data from %s', len(data), host)
        self.peer_buffers[host] += data
        self.handle_messages(host)
