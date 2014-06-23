"""
Implements a small protocol by which the server can be queried and controlled.

Client                     Server
------                     ------

1. Get the IP address of a particular hostname
Name[hostname] ----------->
    <---------------------- IP[ip or None]

2. Get the hostname of a particular IP
IP[ip] ------------------->
    <---------------------- Name[hostname or None]

3. Get the mapping between all hostnames and their IP addresses
GetAll[] ----------------->
    <---------------------- NameIPMapping[name_ip_dict]
"""
from collections import namedtuple
import json
import struct

class Name(namedtuple('Name', ['hostname'])):
    TYPE = 'name'

    @staticmethod
    def from_json(json_dict):
        return Name(json_dict['hostname'])

    def to_dict(self):
        return {'type': 'name', 'hostname': self.hostname}

class IP(namedtuple('IP', ['ip'])):
    TYPE = 'ip'

    @staticmethod
    def from_json(json_dict):
        return IP(json_dict['ip'])

    def to_dict(self):
        return {'type': 'ip', 'ip': self.ip}

class GetAll(namedtuple('GetAll', [])):
    TYPE = 'get-all'

    @staticmethod
    def from_json(json_dict):
        return GetAll()

    def to_dict(self):
        return {'type': 'get-all'}

class NameIPMapping(namedtuple('NameIPMapping', ['name_ips'])):
    TYPE = 'nameipmapping'

    @staticmethod
    def from_json(json_dict):
        return NameIPMapping(json_dict['name_ips'])

    def to_dict(self):
        return {'type': 'nameipmapping', 'name_ips': self.name_ips}

class Quit(namedtuple('Quit', [])):
    TYPE = 'quit'

    @staticmethod
    def from_json(json_dict):
        return Quit()

    def to_dict(self):
        return {'type': 'quit'}

MESSAGE_TYPES = { cls.TYPE: cls
    for cls in (Name, IP, GetAll, NameIPMapping, Quit)}

def send_message(socket, msg):
    """
    Sends a message over a socket, by pickling the message and writing its binary content.
    """
    buffer = json.dumps(msg.to_dict())
    raw_buffer = bytes(buffer, 'utf-8')

    # A hostname can be proto.MSG_SIZE - 1 characters long, which a short will
    # always be long enough for, but an unsigned char may not.
    length_encoded = struct.pack('H', len(raw_buffer))
    socket.send(length_encoded)

    while raw_buffer:
        sent = socket.send(raw_buffer)
        raw_buffer = raw_buffer[sent:]

def recv_message(socket):
    """
    Reconstructs a message from a socket, returning the message object.
    """
    length_encoded = socket.recv(2)
    (length,) = struct.unpack('H', length_encoded)

    raw_buffer = b''
    while len(raw_buffer) < length:
        raw_buffer += socket.recv(length - len(raw_buffer))

    buffer = str(raw_buffer, 'utf-8')
    data = json.loads(buffer)

    constructor = MESSAGE_TYPES[data['type']]
    return constructor.from_json(data)
