"""
Control Protocol
----------------

This implements the inner-facing side of lnsd, which allows the local host to
query the host-name mapping. There are four types of messages, which are
``HOST``, ``IP``, ``GET-ALL``, ``NAME-IP-MAPPING`` and ``QUIT``.

A ``HOST`` message references a hostname, and when sent to the server, it
queries the host-name mapping for that hostname and produces an ``IP`` packet,
which contains a list of IP addresses matching that host.

A ``IP`` message references an IP address, and when sent to the server, it
queries the host-name mapping for that IP address, and produces a ``HOST``
packet containing the hostname assigned to that IP address.

A ``GET-ALL`` message is sent to the server to query the entire host-name
mapping, to which the server replies with a ``NAME-IP-MAPPING`` message
indicating all of the host-name mapping.

A ``QUIT`` message causes the server to terminate.
"""
from collections import namedtuple
import json
import io
import socket
import struct

from . import net_proto, reactor, utils

CONTROL_PORT = 10771

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

        if data['hostname'] is not None:
            net_proto.verify_hostname(data['hostname'].encode('ascii'))

        return Host(data['hostname'])

    def serialize(self):
        """
        Produces a bytestring from this message.
        """
        if self.hostname is not None:
            net_proto.verify_hostname(self.hostname.encode('ascii'))
        return length_encode_json({'type': 'name', 'hostname': self.hostname})

class IP(namedtuple('IP', ['ip_addrs'])):
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

        for ip_addr in data['ip_addrs']:
            verify_ipv4_address(ip_addr)

        return IP(data['ip_addrs'])

    def serialize(self):
        """
        Produces a bytestring from this message.
        """
        return length_encode_json({'type': 'ip', 'ip_addrs': self.ip_addrs})

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
            raise ValueError('Got type {}, expected get-all'.format(
                data['type']))

        return GetAll()

    def serialize(self):
        """
        Produces a bytestring from this message.
        """
        return length_encode_json({'type': 'get-all'})

class NameIPMapping(namedtuple('NameIPMapping', ['host_to_ips'])):
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
            raise ValueError('Got type {}, expected nameipmapping'.format(
                data['type']))

        for name, ip_addrs in data['name_ips'].items():
            net_proto.verify_hostname(name.encode('ascii'))
            for ip in ip_addrs:
                verify_ipv4_address(ip)

        return NameIPMapping(data['name_ips'])

    def serialize(self):
        """
        Produces a bytestring from this message.
        """
        return length_encode_json({'type': 'nameipmapping',
            'name_ips': self.host_to_ips})

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

class ClientHandler:
    """
    Connects to the LNS control port, and sends/retrieves JSON encoded messages
    from the server.
    """
    def __init__(self, port=CONTROL_PORT):
        self.port = port
        self.command_sock = None

    def read_json_message(self, expected_message_type):
        """
        Reads a JSON message from the socket.
        """
        length_header = self.command_sock.recv(2)
        length = struct.unpack('H', length_header)[0]

        recv_message_raw = b''
        while len(recv_message_raw) < length:
            recv_message_raw += self.command_sock.recv(utils.BUFFER_SIZE)

        json_data = get_length_encoded_json(
            io.BytesIO(length_header + recv_message_raw))
        message_class = get_message_class(json_data)
        if message_class is not expected_message_type:
            raise ValueError('Expected a {}, but got a {}'.format(
                expected_message_type, message_class))
        return message_class.unserialize(json_data)

    def __enter__(self):
        self.open()

    def __exit__(self, *exc):
        self.close()

    def open(self):
        """
        Opens up the command socket for sending information.
        """
        self.command_sock = socket.socket()
        self.command_sock.connect(('localhost', self.port))

    def close(self):
        """
        Closes the command socket.
        """
        self.command_sock.close()

    def get_ip(self, host):
        """
        Gets the IP address corresponding to a hostname. Note that the return
        value may be ``None`` if no address corresponds to the given host.
        """
        message = Host(host)
        self.command_sock.send(message.serialize())
        reply = self.read_json_message(IP)
        return reply.ip_addrs

    def get_host(self, ip):
        """
        Gets the host corresponding to an IP address. Note that the return
        value may be ``None`` if no host corresponds to the given address.
        """
        message = IP([ip])
        self.command_sock.send(message.serialize())
        reply = self.read_json_message(Host)
        return reply.hostname

    def get_host_ip_mapping(self):
        """
        Gets the entire host -> IP mapping, as a dictionary.
        """
        message = GetAll()
        self.command_sock.send(message.serialize())
        reply = self.read_json_message(NameIPMapping)
        return reply.host_to_ips

class ProtocolHandler:
    """
    Handles clients on the local machine, which connect to query the host-ip
    mapping in different ways.
    """
    def __init__(self, network_handler, a_reactor, port=CONTROL_PORT):
        self.reactor = a_reactor
        self.port = port
        self.server_sock = None
        self.clients = {}
        self.client_buffers = {}
        self.done = False

        self.network_handler = network_handler

    def is_running(self):
        """
        Returns whether or not this control server is still active.
        """
        return not self.done

    def open(self):
        """
        Opens up the command socket for processing clients.
        """
        self.server_sock = socket.socket()
        self.server_sock.bind(('localhost', self.port))
        self.server_sock.listen(5)
        self.server_sock.setblocking(False)
        self.reactor.bind(self.server_sock, reactor.READABLE, self.on_connect)

    def close(self):
        """
        Closes the server, as well as any active clients.
        """
        to_close = [sock for sock in self.clients.values()]
        for sock in to_close:
            self.close_client(sock)

        self.reactor.unbind(self.server_sock)
        self.server_sock.close()

    def on_connect(self, event):
        """
        Handle a connection on the server.
        """
        client, _ = self.server_sock.accept()
        self.clients[client.fileno()] = client
        self.client_buffers[client.fileno()] = b''
        self.reactor.bind(client, reactor.READABLE, self.on_message_recv)

    def close_client(self, client_sock):
        """
        Closes the client with the given file descriptor, and destroys its
        buffer.
        """
        client_fd = client_sock.fileno()
        if client_fd == -1:
            return

        self.reactor.unbind(client_sock)
        client_sock.close()

        del self.clients[client_fd]
        del self.client_buffers[client_fd]

    def pull_messages(self, client_fd, client_sock):
        """
        Pulls out messages from the client's buffer, until there aren't any
        full messages to remove.
        """
        client_buffer_stream = utils.TransactionalBytesIO(
            self.client_buffers[client_fd])
        while True:
            json_message = None
            with client_buffer_stream.get_transaction() as txn:
                txn_stream = txn.get_stream()
                try:
                    # Note that we don't want to affect the read position if
                    # no message is there, so use the transaction to save
                    # the position and only update it when we're sure we
                    # have a message.
                    json_message = get_length_encoded_json(txn_stream)
                    txn.commit()
                except EOFError:
                    txn.abort()
                    break
                except ValueError:
                    pass

            # This indicates an invalid message, because we read the whole
            if json_message is None:
                continue

            message_class = get_message_class(json_message)
            message = message_class.unserialize(json_message)
            self.handle_message(client_sock, message)

        self.client_buffers[client_fd] = client_buffer_stream.read()

    def on_message_recv(self, event):
        """
        Handles a message sent by a client.
        """
        client_fd, _ = event
        client_sock = self.clients[client_fd]
        try:
            chunk = client_sock.recv(utils.BUFFER_SIZE)
            if not chunk:
                self.close_client(client_sock)
                return
            self.client_buffers[client_fd] += chunk
            self.pull_messages(client_fd, client_sock)
        except OSError:
            # This happened occasionally during testing, causing the tests to
            # crash
            if client_sock.fileno() != -1:
                self.close_client(client_sock)

    def handle_message(self, client, message):
        """
        Processes the given message which was received from the given client.
        """
        reply = None
        if isinstance(message, Host):
            ip_addrs = self.network_handler.query_host(message.hostname)
            reply = IP(ip_addrs)
        elif isinstance(message, IP):
            if len(message.ip_addrs) == 1:
                hostname = self.network_handler.query_ip(message.ip_addrs[0])
                reply = Host(hostname)
        elif isinstance(message, GetAll):
            host_ip_mapping = self.network_handler.get_host_ip_map()
            reply = NameIPMapping(host_ip_mapping)
        elif isinstance(message, Quit):
            self.done = True

        if reply is not None:
            client.sendall(reply.serialize())
