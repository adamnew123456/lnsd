"""
Various Utilities
-----------------

These are various functions which don't have any direct dependency upon the
state of the rest of the programs.
"""

class Token:
    """
    A unique value, like ``object()``, but which has a nice string 
    representation.

        >>> A = Token('A')
        >>> A
        <A>
        >>> str(A)
        '<A>'
        >>> repr(A)
        '<A>'
    """
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return '<' + self.name + '>'

    def __repr__(self):
        return '<' + self.name + '>'

def to_iterable(x, preferred_type=list):
    """
    Converts an object into an object which can be iterated (or, if a
    preferred type is given, into an object of the preferred type).

        >>> to_iterable(1)
        [1]
        >>> to_iterable(1, preferred_type=set)
        {1}
        >>> to_iterable(1, preferred_type=tuple)
        (1,)
        >>> to_iterable([1])
        [1]
        >>> to_iterable((1,))
        [1]
        >>> to_iterable({1})
        [1]
    """
    try:
        iter(x)
        return preferred_type(x)
    except TypeError:
        return preferred_type([x])

def to_file_descriptor(fobj):
    """
    Converts an object to a file descriptor. The given object can be either:

     - An integer file descriptor
     - An object with a ``fileno()`` method.

    :raises ValueError: If the given object cannot be converted.

        >>> class Descriptable:
        ...     def fileno(self):
        ...         return 42
        ...
        >>> to_file_descriptor(Descriptable())
        42
        >>> to_file_descriptor(42)
        42
        >>> try:
        ...     to_file_descriptor(object())
        ... except ValueError:
        ...     print('Failure')
        ...
        Failure
    """
    if isinstance(fobj, int):
        return fobj
    elif hasattr(fobj, 'fileno'):
        return fobj.fileno()
    else:
        raise ValueError(
            '{} cannot be converted to a file descriptor'.format(fobj))

def sendto_all(sock, buffer, addr):
    """
    Like :meth:`socket.socket.sendall`, but using :meth:`sokcet.socket.sendto`.
    """
    while buffer:
        sent = sock.sendto(buffer, addr)
        buffer = buffer[sent:]
