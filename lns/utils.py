"""
Various Utilities
-----------------

These are various functions which don't have any direct dependency upon the
state of the rest of the programs.
"""
import io
import sys

# Most messages should be fairly small, and should fit inside of this limit
BUFFER_SIZE = 1024

class TransactionalBytesIO(io.BytesIO):
    """
    Like :class:`io.BytesIO`, but supports transactions, where a transaction may
    initialized; when initialized, the transaction produces its own internal
    stream, where changes will only be reflected in the original stream if the
    transaction is committed.

    Writes will not succeed unless committed::

        >>> stream = TransactionalBytesIO(b'cool story, bro')
        >>> with stream.get_transaction() as txn:
        ...     txn_stream = txn.get_stream()
        ...     _ = txn_stream.write(b'blah blah')
        ...     txn_content = txn_stream.getvalue()
        ...     txn.abort()
        ...
        >>> txn_content
        b'blah blahy, bro'
        >>> stream.getvalue()
        b'cool story, bro'

    Neither will changes in position due to reads or seeks::

        >>> old_pos = stream.tell()
        >>> with stream.get_transaction() as txn:
        ...     txn_stream = txn.get_stream()
        ...     _ = txn_stream.seek(old_pos + 1)
        ...     txn_pos = txn_stream.tell()
        ...     txn.abort()
        ...
        >>> assert stream.tell() == old_pos
        >>> assert txn_pos == old_pos + 1

    The only way to change these attributes of the stream is to commit the
    transaction::

        >>> with stream.get_transaction() as txn:
        ...     txn_stream = txn.get_stream()
        ...     _ = txn_stream.write(b'what')
        ...     txn_pos = txn_stream.tell()
        ...     txn.commit()
        ...
        >>> stream.getvalue()
        b'what story, bro'
        >>> assert stream.tell() == txn_pos
    """
    class BytesIOTransaction:
        """
        Contains all the state of a BytesIO transaction.
        """
        def __init__(self, parent):
            self.parent = parent
            self.position = parent.tell()
            self.buffer = parent.getvalue()

            self.stream = TransactionalBytesIO(self.buffer)
            self.stream.seek(self.position)

        def get_stream(self):
            """
            Gets the stream used by this transaction.
            """
            return self.stream

        def commit(self):
            """
            Commits the transaction, applying the changes to the underling
            stream.
            """
            if self.parent.getvalue() != self.stream.getvalue():
                self.parent.truncate(0)
                self.parent.seek(0)

                self.parent.write(self.stream.getvalue())
            self.parent.seek(self.stream.tell())

        def abort(self):
            """
            Discards the current transaction. This technically doesn't do
            anything, but calling it shows your intention.
            """

        def __enter__(self):
            return self

        def __exit__(self, *exn):
            self.abort()

    def get_transaction(self):
        "Gets a new transaction on top of this current stream."
        return self.BytesIOTransaction(self)

def sendto_all(sock, buffer, addr):
    """
    Like :meth:`socket.socket.sendall`, but using :meth:`sokcet.socket.sendto`.
    """
    while buffer:
        sent = sock.sendto(buffer, addr)
        buffer = buffer[sent:]
