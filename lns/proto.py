"""
A implementation of the LNS protocol.

This module provides both basic packet routines, as well as the network handler.
"""

from collections import namedtuple
import select
import socket
import struct
import sys
import time

Announce = namedtuple('Announce', ['name'])
Conflict = namedtuple('Conflict', [])

BROADCAST = '255.255.255.255'
MSG_SIZE = 512
ANNOUNCE, CONFLICT = (1, 2)
def get_message(raw):
    """
    Takes a raw message, and converts it into either an Announce or a Conflict.
    If the message is invalid, this returns None.
    """
    pkt_type = raw[0]
    raw = raw[1:] # Trim off the message identifier
    if pkt_type == ANNOUNCE:
        # Since NUL bytes are used for packing, find the first and take everything
        # before it.
        first_nul = raw.find(b'\0')
        if first_nul > -1:
            name= raw[:first_nul]
        else:
            name = raw
        
        # Although the client which is asserting that is has this name should do
        # some checking on its own, we should go ahead and ensure that it is
        # correct anyway.
        for ascii_code in name:
            if ascii_code <= 32 or ascii_code == 127:
                return None

        return Announce(name)
    elif pkt_type == CONFLICT:
        return Conflict()
    else:
        return None

def send_message(sock, message, recipient):
    """
    Sends out the given message over a socket.
    """
    if isinstance(message, Conflict):
        raw = struct.pack('>B', CONFLICT)
        raw += b'\0' * (MSG_SIZE - 1)
    elif isinstance(message, Announce):
        raw = struct.pack('>B', ANNOUNCE)
        raw += message.name
        raw += b'\0' * (MSG_SIZE - 1 - len(message.name))
    sock.sendto(raw, recipient)

SECONDS = 1000
def protocol_handler(lnsd):
    """
    Implements the LNS protocol.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setblocking(True)

    sock.bind((BROADCAST, lnsd.port))

    pollster = select.poll()
    pollster.register(sock, select.POLLIN)

    # The timestamp of the last message from each host - this is used to
    # determine when a client should be dropped
    age = {}

    # How long since we sent out our last announce message
    last_heartbeat = 0
    
    while True:
        # This event is set by the DBus thread, in response to a user-initiated 
        # quit signal
        if lnsd.quit_event.is_set():
            sock.close()
            return

        # Figure out how long until the next heartbeat occurs
        now = time.time()
        till_heartbeat = max(lnsd.heartbeat - (now - last_heartbeat), 0)

        events = pollster.poll(till_heartbeat * SECONDS)

        # If it's time, send out the next heartbeat message - don't let any
        # negative numbers in, since that tells the pollster to wait
        # indefinitely
        now = time.time()
        if now - last_heartbeat >= lnsd.heartbeat:
            send_message(sock, Announce(lnsd.name), (BROADCAST, lnsd.port))
            last_heartbeat = now

        # (We can drop the event and the file descriptor, since those are
        # known)
        for _ in events:
            raw, sender = sock.recvfrom(MSG_SIZE)
            message = get_message(raw)
            sender_ip, _ = sender
            age[sender_ip] = time.time()
            
            if isinstance(message, Announce):
                if message.name in ~lnsd.host_names:
                    # Figure out if this is a collision, by seeing if another
                    # host has the same name.
                    other_owner = lnsd.host_names[:message.name]

                    if other_owner != sender_ip:
                        # This is a name collision - alert the sender that they're
                        # colliding with another host
                        send_message(sock, Conflict(), (BROADCAST, lnsd.port))
                        continue
                
                # Get rid of any previous mapping this host had, and assign it
                # a new name
                with lnsd.host_names_lock:
                    if sender_ip in lnsd.host_names:
                        del lnsd.host_names[sender_ip:]
                    lnsd.host_names[sender_ip:] = message.name

            elif isinstance(message, Conflict):
                # We're dead in the water - there's no way for the user to
                # change this, so go ahead and die.
                sys.exit(2)
         
        # Remove entries for hosts which haven't sent us anything recently
        now = time.time()
        to_delete = []
        for host, last_message in age.items():
            if now - last_message > lnsd.timeout:
                to_delete.append(host)

        with lnsd.host_names_lock:
            while to_delete:
                host = to_delete.pop()
                del lnsd.host_names[host:]
                del age[host]
