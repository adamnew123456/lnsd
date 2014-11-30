"""
Various Utilities
-----------------

These are various functions which don't have any direct dependency upon the
state of the rest of the programs.
"""
def sendto_all(sock, buffer, addr):
    """
    Like :meth:`socket.socket.sendall`, but using :meth:`sokcet.socket.sendto`.
    """
    while buffer:
        sent = sock.sendto(buffer, addr)
        buffer = buffer[sent:]
