"""
Network Protocol
----------------

This implements the network-facing side of lnsd. There are only two types of
messages, ``ANNOUNCE`` and ``CONFLICT``.

An ``ANNOUNCE`` packet is sent periodically to ensure that a host is still on a
network, and that it is asserting a particular hostname. If another host 
discovers that there is a name clash, it sends a ``CONFLICT`` to the host with
the duplicate name. When a host receives a ``CONFLICT`` packet, the host should
shut down its server until the name clash can be resolved.

In the indefinite future, I plan to remove ``CONFLICT`` from the protocol, and
simply allow lnsd to tolerate hosts with the same name.
"""
from collections import namedtuple

# All packets received from the network are 512 bytes, not including the UDP
# header
PACKET_SIZE = 512

def verify_hostname(hostname_bytes):
    """
    Verifies a hostname, to ensure that it is valid ASCII and that it doesn't
    contain any unprintable characters.

    It returns the encoded version of the hostname if it succeeds, otherwise it
    raises a :class:`ValueError`.
    """
    if not hostname_bytes or len(hostname_bytes) > PACKET_SIZE - 1:
        raise ValueError('Encoded hostname is not between 0 and {} bytes'.format(
            PACKET_SIZE - 1))

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
            raise ValueError('Header byte incorrect - got {}, expected 0x01'.format(
                hex(header)))

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
            raise ValueError('Hostname too long - it can be {} bytes at most'.format(
                PACKET_SIZE - 1))

        return b'\x01' + raw_hostname.ljust(PACKET_SIZE - 1, b'\x00')

class Conflict(namedtuple('Conflict', [])):
    HEADER = 0x02

    @staticmethod
    def parses(buffer):
        """
        Returns ``True`` if this class can parse the given buffer, or
        ``False`` otherwise.
        """
        return buffer and buffer[0] == Conflict.HEADER

    @staticmethod
    def unserialize(buffer):
        """
        Produces a :class:`Conflict` message from the contents of a buffer.
        """
        if len(buffer) != PACKET_SIZE:
            raise ValueError('Packet not the correct length - '
                '{} bytes, expected {}'.format(len(buffer, PACKET_SIZE)))

        header = buffer[0]
        if header != Conflict.HEADER:
            raise ValueError('Header byte incorrect - got {}, expected 0x02'.format(
                hex(header)))

        return Conflict()

    def serialize(self):
        """
        Produces a bytestring from this message.
        """
        return b'\x02'.ljust(PACKET_SIZE, b'\x00')

MESSAGE_CLASSES = {Announce, Conflict}
def get_message_class(buffer):
    """
    Gets the message class capable of parsing the given buffer.

    :raises ValueError: If the given message cannot be handled by any class.
    """
    for msg_class in MESSAGE_CLASSES:
        if msg_class.parses(buffer):
            return msg_class
    raise ValueError('Could not parse the given buffer')
