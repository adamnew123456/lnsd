"""
Control Protocol
----------------

This implements the inner-facing side of lnsd, which allows the local host to
query the host-name mapping. There are four types of messages, which are 
``HOST``, ``IP``, ``GET-ALL``, ``NAME-IP-MAPPING`` and ``QUIT``.

A ``HOST`` message references a hostname, and when sent to the server, it
queries the host-name mapping for that hostname and produces an ``IP`` packet.

A ``IP`` message references an IP address, and when sent to the server, it
queries the host-name mapping for that IP address, and produces a ``HOST``
packet.

A ``GET-ALL`` message is sent to the server to query the entire host-name mapping,
to which the server replies with a ``NAME-IP-MAPPING`` message indicating all
of the host-name mapping.

A ``QUIT`` message causes the server to terminate.
"""
from collections import namedtuple
import json
import io
import struct

from . import net_proto

def get_length_encoded_json(stream):
    """
    Reads a JSON string from a bytestream, producing a dictionary.

    :raises EOFError: If the stream isn't long enough.
    """
    length_bytes = stream.read(2)
    if len(length_bytes) != 2:
        raise EOFError

    length = struct.unpack('H', length_bytes)[0]
    json_bytes = stream.read(length)
    if len(json_bytes) != length:
        raise EOFError

    json_str = json_bytes.decode('utf-8')
    return json.loads(json_str)

def length_encode_json(data):
    """
    Produces a length-encoded representation of JSON.
    """
    json_bytes = json.dumps(data).encode('utf-8')
    length_header = struct.pack('H', len(json_bytes))
    return length_header + json_bytes

def verify_ipv4_address(text):
    """
    Ensures the correctness of a textual IPv4 address.
    """
    octets = text.split('.')
    if len(octets) != 4:
        raise ValueError('Wrong number of dotted segments in IP address')

    for octet in octets:
        int_octet = int(octet)
        if int_octet < 0 or int_octet > 255:
            raise ValueError('Octets must be between 0-255 inclusive')

class Host(namedtuple('Host', ['hostname'])):
    TYPE = 'name'

    @staticmethod
    def parses(data):
        """
        Returns ``True`` if this class can parse the given dictionary, or 
        ``False`` otherwise.
        """
        return data['type'] == 'name'

    @staticmethod
    def unserialize(data):
        """
        Produces a :class:`Host` message from the contents of a dictionary.

        :raises EOFError: If the stream is not long enough, 
        """
        if data['type'] != 'name':
            raise ValueError('Got type {}, expected name'.format(data['type']))

        net_proto.verify_hostname(data['hostname'].encode('ascii'))
        return Host(data['hostname'])

    def serialize(self):
        """
        Produces a bytestring from this message.
        """
        net_proto.verify_hostname(self.hostname.encode('ascii'))
        return length_encode_json({'type': 'name', 'hostname': self.hostname})
        
class IP(namedtuple('IP', ['ip'])):
    TYPE = 'ip'

    @staticmethod
    def parses(data):
        """
        Returns ``True`` if this class can parse the given dictionary, or 
        ``False`` otherwise.
        """
        return data['type'] == 'ip'

    @staticmethod
    def unserialize(data):
        """
        Produces a :class:`IP` message from the contents of a dictionary.

        :raises EOFError: If the stream is not long enough, 
        """
        if data['type'] != 'ip':
            raise ValueError('Got type {}, expected ip'.format(data['type']))

        verify_ipv4_address(data['ip'])
        return IP(data['ip'])

    def serialize(self):
        """
        Produces a bytestring from this message.
        """
        return length_encode_json({'type': 'ip', 'ip': self.ip})

class GetAll(namedtuple('GetAll', [])):
    TYPE = 'get-all'

    @staticmethod
    def parses(data):
        """
        Returns ``True`` if this class can parse the given dictionary, or 
        ``False`` otherwise.
        """
        return data['type'] == 'get-all'

    @staticmethod
    def unserialize(data):
        """
        Produces a :class:`GetAll` message from the contents of a dictionary.

        :raises EOFError: If the stream is not long enough, 
        """
        if data['type'] != 'get-all':
            raise ValueError('Got type {}, expected get-all'.format(data['type']))

        return GetAll()

    def serialize(self):
        """
        Produces a bytestring from this message.
        """
        return length_encode_json({'type': 'get-all'})

class NameIPMapping(namedtuple('NameIPMapping', ['host_to_names'])):
    TYPE = 'nameipmapping'

    @staticmethod
    def parses(data):
        """
        Returns ``True`` if this class can parse the given dictionary, or 
        ``False`` otherwise.
        """
        return data['type'] == 'nameipmapping'

    @staticmethod
    def unserialize(data):
        """
        Produces a :class:`GetAll` message from the contents of a dictionary.

        :raises EOFError: If the stream is not long enough, 
        """
        if data['type'] != 'nameipmapping':
            raise ValueError('Got type {}, expected nameipmapping'.format(data['type']))

        for name, ip in data['name_ips'].items():
            net_proto.verify_hostname(name.encode('ascii'))
            verify_ipv4_address(ip)
        return NameIPMapping(data['name_ips'])

    def serialize(self):
        """
        Produces a bytestring from this message.
        """
        return length_encode_json({'type': 'nameipmapping', 'name_ips': self.host_to_names})

class Quit(namedtuple('Quit', [])):
    TYPE = 'quit'

    @staticmethod
    def parses(data):
        """
        Returns ``True`` if this class can parse the given dictionary, or 
        ``False`` otherwise.
        """
        return data['type'] == 'quit'

    @staticmethod
    def unserialize(data):
        """
        Produces a :class:`Quit` message from the contents of a dictionary.

        :raises EOFError: If the stream is not long enough, 
        """
        if data['type'] != 'quit':
            raise ValueError('Got type {}, expected quit'.format(data['type']))

        return Quit()

    def serialize(self):
        """
        Produces a bytestring from this message.
        """
        return length_encode_json({'type': 'quit'})

MESSAGE_CLASSES = {Host, IP, GetAll, NameIPMapping, Quit}
def get_message_class(data):
    """
    Gets the message class capable of parsing the given dictionary.

    :raises ValueError: If the given message cannot be handled by any class.
    """
    for msg_class in MESSAGE_CLASSES:
        if msg_class.parses(data):
            return msg_class
    raise ValueError('Could not parse the given dictionary')
