"""
Utilities and constants used in multiple modules.
"""
import socket
import struct

# An arbitrating data for running a proxy
CHUNK = 1024 * 1024

# Commands that a SOCKS client can send to the server
CMD_CONNECT, CMD_BIND, CMD_ASSOCIATE = bytes([1,2,3])

# Address types that clients can use for addresses
ADDR_IP4, ADDR_DOMAIN, ADDR_IP6 = bytes([1,3,4])

lns_service = None
def set_lnsd(lnsd):
    """
    Configures the LNS provider which gives us our LAN IP addresses.
    """
    global lns_service
    lns_service = lnsd

def get_real_address(address, port):
    """
    Gets the address family and address associated with a particular host and port.
    """ 
    if address.endswith('.lan'):
        with lns_service.host_names_lock:
            try:
                lns_name = bytes(address.replace('.lan', ''), 'ascii')
                names_hosts = ~lns_service.host_names
                address = names_hosts[lns_name]
            except KeyError:
                pass
    addr_infos = socket.getaddrinfo(address, port)
    if addr_infos:
        family, _, _, _, addr = addr_infos[0]
        return family, addr
    else:
        raise OSError('Cannot resolve "{}" on port {}'.format(address, port))

def get_sockname(sock_name):
    """
    Gets the address of a socket connection as bytes.
    @param sock_name The value from either .getsockname() or .getpeername().
    @return The address type, the address in bytes, and the port.
    """
    # Figure out if the peer is using IPv4 or IPv6
    addr_family = (socket.AF_INET 
            if len(sock_name) == 2 # (host, port)
            else socket.AF_INET6) # (host, port, flowinfo, scopeid)
    
    addr_type = (ADDR_IP4
            if addr_family == socket.AF_INET
            else ADDR_IP6)

    return addr_type, socket.inet_pton(addr_family, sock_name[0]), sock_name[1]

def send_sock_info(channel, sockname):
    """
    Sends the .getpeername() or .getsockname() information over the channel
    according to SOCKS5 protocol
    """
    addr_type, bytes_addr, port = get_sockname(sockname)

    # 0x05: SOCKS v5
    # 0x00: Success
    # 0x00: Reserved
    message = struct.pack('!BBBB', 5, 0, 0, addr_type)
    message += bytes_addr
    message += struct.pack('!H', port)
    channel.send(message)

def ip_to_text(bytestr, sep):
    """
    Converts an IPv4 or IPv6 address to plain text.
    """
    return sep.join(str(byte) for byte in bytestr)

def read_bytes(sock, n):
    """
    Reads bytes from the given socket, ensuring exactly n bytes are read.
    """
    buffer = b''
    bufflen = len(buffer)
    while bufflen < n:
        chunk = sock.recv(n - bufflen)
        if not chunk:
            # The other end has dropped, which is most likely an error
            raise IOError('Peer of {} has dropped'.format(sock))

        buffer += chunk
        bufflen = len(buffer)
    return buffer
