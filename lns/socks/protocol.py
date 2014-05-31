"""
Handles different aspects of the SOCKS protocol.
"""

import io
import socket
import struct

from lns.socks.utils import *

class PreSession:
    """
    Dispatches to different session types, and parses SOCKS requests.
    """
    def __init__(self, manager, client):
        self.manager = manager
        self.session = manager.start()
        self.session.register(client.fileno(), self._handle_request)

        self.client = client
        client.setblocking(False)

        # The first part of the request is authentication, the second part
        # is the request itself
        self.has_authenticated = False

    def _authenticate(self):
        """
        Authenticates the client before moving on. No actual authentication is
        required, but this is a necessary part of the protocol.
        """
        # First, figure out which authentication methods are avaialble
        auth_header = read_bytes(self.client, 2)

        (_, n_methods) = struct.unpack('!BB', auth_header)
        auth_methods = read_bytes(self.client, n_methods)

        # Then, see if the client can accept no authentication
        if b'\x00' in auth_methods: # Client will work unauthenticated
            #  0x05 = SOCKS v5 Header
            #  0x00 = Use no authentication
            self.client.send(b'\x05\x00')
            self.has_authenticated = True

        else: # Client will not work unauthenticated
            # 0x05 = SOCKS v5 Header
            # 0xff = No authentication method found
            self.client.send(b'\x05\xff')
            self.session.stop(close=True)

    def _handle_command(self):
        """
        Handles a SOCKS request, after authentication.
        """
        # First, get the SOCKS request
        request = read_bytes(self.client, 4)
        _, command, _, addr_type = struct.unpack('!BBBB', request)
        
        # Then, figure out how to consume the address and convert it into
        # a plain-text format
        if addr_type == ADDR_IP4:
            addr = read_bytes(self.client, 4)
            text_addr = ip_to_text(addr, '.')
        elif addr_type == ADDR_IP6:
            addr = read_bytes(self.client, 6)
            text_addr = ip_to_text(addr, ':')
        elif addr_type == ADDR_DOMAIN:
            domain_length = read_bytes(self.client, 1)[0]
            domain_bytes = read_bytes(self.client, domain_length)
            text_addr = str(domain_bytes, 'ascii')
        else:
            raise IOError('Invalid address type {}'.format(addr_type))

        port = struct.unpack('!H', read_bytes(self.client, 2))[0]
        
        # Pick out which type of session we're to transition into
        if command == CMD_CONNECT:
            session_type = ConnectSession
        elif command == CMD_BIND:
            session_type = BindSession
        elif command == CMD_ASSOCIATE:
            session_type = AssociateSession
        else:
            raise IOError('Invalid request {}'.format(command))

        # Hand off control to the next session, without closing
        # our file descriptors
        self.session.stop(close=False)
        
        # Create a specialized session which can handle this request
        next_session = session_type(self.manager, self.client,
                text_addr, port)

    def _handle_request(self, fileno):
        """
        Handles a request from a client, and dispatches it to another session.
        """
        if not self.has_authenticated:
            self._authenticate()
        else:
            self._handle_command()

class ConnectSession:
    """
    Handles SOCKS CONNECT requests, which is basically acting as a TCP relay.
    """
    def __init__(self, manager, client, address, port):
        self.session = manager.start()
        self.client = client
        self.session.register(client.fileno(), self._handle_data)

        try:
            real_family, real_address = get_real_address(address, port)
            self.peer = socket.socket(real_family, socket.SOCK_STREAM)
            self.peer.connect(real_address)
            self.peer.setblocking(False)
            self.session.register(self.peer.fileno(), self._handle_data)

            send_sock_info(self.client, self.peer.getsockname())

            self.fd_map = {
                self.client.fileno(): (self.client, self.peer),
                self.peer.fileno(): (self.peer, self.client),
            }
        except (OSError, socket.gaierror):
            # Failed to locate the given host
            self._send_host_error()
            self.session.stop(close=True)
        except ConnectionRefusedError:
            self._send_port_error()
            self.session.stop(close=True)

    def __str__(self):
        try:
            client_name = self.client.getpeername()
        except OSError:
            client_name = 'disconnected'

        try:
            peer_name = self.peer.getpeername()
        except OSError:
            peer_name = 'disconnected'

        return "<CONNECT: {} <---> {}>".format(
                client_name,
                peer_name)

    def _send_host_error(self):
        """
        Sends back a response indicating a failure due to hostname resolution.
        """
        # 0x05: SOCKS v5
        # 0x04: Host unreachable
        # 0x00: Resserved
        # 0x01: Address type (IPv4)
        # 0x00 0x00 0x00 0x00: Garbage IP addressj
        # 0x00 0x00: Garbage port
        self.client.send(bytes([5,4,0,1,0,0,0,0,0,0]))
    
    def _send_port_error(self):
        """
        Sends back a response indicating a failure to connect to the given port.
        """
        # 0x05: SOCKS v5
        # 0x05: Connection refused
        # 0x00: Resserved
        # 0x01: Address type (IPv4)
        # 0x00 0x00 0x00 0x00: Garbage IP addressj
        # 0x00 0x00: Garbage port
        self.client.send(bytes([5,5,0,1,0,0,0,0,0]))

    def _handle_data(self, fileno):
        """
        Passes a chunk of data between the peers.
        """
        source, dest = self.fd_map[fileno]
        data = source.recv(CHUNK)
        if not data:
            # An empty receive means that a connection has closed
            self.session.stop(close=True)
        else:
            dest.send(data)

class BindSession:
    """
    Similar to ConnectSession, but the connection is initiated by the peer
    instead of us, the server.
    """
    def __init__(self, manager, client, address, port):
        self.session = manager.start()
        self.client = client

        self.server = socket.socket()
        self.server.setblocking(False)
        self.server.bind(('', 0))
        self.server.listen(1)
        self.session.register(self.server.fileno(), self._handle_server_connection)

        # Tell the client that we're listening
        send_sock_info(self.client, self.server.getsockname())

    def __str__(self):
        try:
            client_name = self.client.getpeername()
        except OSError:
            client_name = 'disconnected'

        if hasattr(self, 'server'):
            return '<BIND: waiting - {}>'.format(client_name)
        else:
            try:
                peer_name = self.peer.getpeername()
            except OSError:
                peer_name = 'disconnected'
            return '<BIND: {} <---> {}>'.format(client_name, peer_name)

    def _handle_server_connection(self, fileno):
        """
        Accepts the server connection, and starts passing data.
        """
        # Open up and register the peer for events
        self.peer, peer_addr = self.server.accept()
        self.peer.setblocking(False)
        self.session.register(self.peer.fileno(), self._handle_data)

        # Create the file descriptor mapping table
        self.fd_map = {
            self.client.fileno(): (self.client, self.peer),
            self.peer.fileno(): (self.peer, self.client),
        }

        # Close the server, since the BIND request is strictly 1-to-1
        self.session.unregister(self.server.fileno())
        self.server.close()
        del self.server

        # Send out the connection details to the client, then listen for data
        # from the client
        send_sock_info(self.client, peer_addr)
        self.session.register(self.client.fileno(), self._handle_data)

    def _handle_data(self, fileno):
        """
        Marshals data between the peer and the client.
        """
        source, dest = self.fd_map[fileno]

        data = source.recv(CHUNK)
        if not data:
            self.session.stop(close=True)
        else:
            dest.send(data)

class AssociateSession:
    """
    Forwards UDP datagrapms over the network, according to the SOCKS protocol.
    """
    def __init__(self, manager, client, address, port):
        self.session = manager.start()
        self.client = client
        self.session.register(self.client.fileno(), self._handle_control_data)

        self.relay = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.relay.setblocking(False)
        self.relay.bind(('', 0))
        self.session.register(self.relay.fileno(), self._handle_relay_data)

        self.source_address = self.client.getpeername()[0]
        send_sock_info(self.client, self.relay.getsockname())

    def __str__(self):
        try:
            client_name = self.client.getpeername()
        except OSError:
            client_name = 'disconnected'

        return '<UDP: held open by {}>'.format(client_name)

    def _handle_control_data(self, fileno):
        """
        Waits for the closure of the control socket - according to the RFC, when
        the control socket closes, the UDP association ends.
        """
        self.session.stop(close=True)

    def _handle_relay_data(self, fileno):
        """
        Handles each UDP packet, which has its own SOCKS header, and relays it.

        Note that this implementation does not support fragmentation.
        """
        data, sender = self.relay.recvfrom(CHUNK)

        # Drop packets not from our associated host
        if sender[0] != self.source_address:
            return

        stream = io.BytesIO(data)
        _, frag, addr_type = struct.unpack('!HBB', stream.read(4))
        if frag > 0:
            # Drop fragmented packets
            return

        # Consume the address and interpret it
        if addr_type == ADDR_IP4:
            addr = stream.read(4)
            text_addr = ip_to_text(addr, '.')
        elif addr_type == ADDR_IP6:
            addr = stream.read(6)
            text_addr = ip_to_text(addr, ':')
        elif addr_type == ADDR_DOMAIN:
            domain_length = stream.read(1)
            domain_bytes = stream.read(domain_length)
            text_addr = str(domain_bytes, 'ascii')
        else:
            # Don't kill the association, just drop this packet
            return
        
        port = struct.unpack('!H', stream.read(2))
        data = stream.read()
        
        real_family, real_address = get_real_address(address, port)
        self.temp_socket = socket.socket(real_family, socket.SOCK_DGRAM)
        self.temp_socket.sendto(data, real_address)
        self.temp_socket.close()
