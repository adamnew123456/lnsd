"""
A way to manage the lifetime of sockets, and to listen to them.
"""
import os
import select
import socket
import struct

from lns.socks.protocol import PreSession
from lns.socks.utils import *

SECONDS = 1000
class SessionManager:
    """
    Manages different sessions, which manage requests from different clients.
    """
    def __init__(self, lnsd, socks_port):
        # Ensure that the utils module gets a reference to the LNS provider,
        # since it needs it to lookup LAN names
        set_lnsd(lnsd)
        self.lnsd = lnsd
        
        self.fds = {}
        self.pollster = select.poll()
        self.done = False

        # Bind the control socket and start listening to it
        self.server = socket.socket()
        self.server.setblocking(False)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(('', socks_port))
        self.server.listen(10)
        self.pollster.register(self.server, select.POLLIN | select.POLLHUP)

    def start(self):
        """
        Returns a new Session.
        """
        return Session(self)

    def register_socket(self, fileno, session):
        """
        Registers a particular file handle with a session.
        """
        self.pollster.register(fileno, select.POLLIN | select.POLLHUP)
        self.fds[fileno] = session

    def unregister_socket(self, fileno):
        """
        Unregisters a particular file handle with a session.
        """
        # If the socket doesn't exist, than that error isn't critical and we
        # can survive it
        try:
            self.pollster.unregister(fileno)
            del self.fds[fileno]
        except KeyError:
            pass

    def run(self):
        """
        Handles all socket events and dispatches to the proper session.
        """
        while not self.done:
            if self.lnsd.quit_event.is_set():
                self.close_all()
                break

            for fileno, event in self.pollster.poll(5 * SECONDS):
                if fileno == self.server.fileno():
                    client, _ = self.server.accept()
                    session = PreSession(self, client)

                if (event & select.POLLIN) and (fileno in self.fds):
                    session = self.fds[fileno]
                    try:
                        session.handle(fileno)
                    except (IOError, BrokenPipeError, ConnectionResetError):
                        session.stop(close=True)
                    except BlockingIOError:
                        pass

                if (event & select.POLLHUP) and (fileno in self.fds):
                    session = self.fds[fileno]
                    session.stop(close=True)

    def close_all(self):
        """
        Terminates all sessions.
        """
        for fd in self.fds:
            os.close(fd)

        self.server.close()
        self.done = True

IN, OUT, HUP = select.POLLIN, select.POLLOUT, select.POLLHUP
class Session:
    """
    Manages the lifetime of sockets, and signals when sockets are managed.
    """
    def __init__(self, manager):
        self.manager = manager
        self.fds = {}

    def register(self, fileno, callback):
        """
        Registers a file descriptor with a callback when events occur on it.
        """
        self.manager.register_socket(fileno, self)
        self.fds[fileno] = callback

    def unregister(self, fileno):
        """
        Unregisters a file descriptor for events.
        """
        assert fileno in self.fds
        self.manager.unregister_socket(fileno)
        del self.fds[fileno]

    def stop(self, close=False):
        """
        End this session, and all sockets associated with it.
        @param close Controls whether or not all the file descriptors are closed.
        """
        existing_fds = set(self.fds)
        for fd in existing_fds:
            self.unregister(fd)

            if close:
                os.close(fd)

    def handle(self, fileno):
        """
        Handles an event on one of our file descriptors by passing it off.
        """
        assert fileno in self.fds
        callback = self.fds[fileno]
        return callback(fileno)
