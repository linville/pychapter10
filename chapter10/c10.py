
import atexit
import os
import struct

from .packet import Packet
from .buffer import Buffer


class C10(object):
    """A Chapter 10 parser."""

    def __init__(self, f, lazy=False):
        """Takes a file or filename and reads packets."""

        atexit.register(self.close)
        if isinstance(f, str):
            f = open(f, 'rb')
        self.file = f
        self.lazy = lazy

    @classmethod
    def from_string(cls, s):
        return cls(Buffer(s))

    def close(self):
        """Make sure we close our file if we can."""

        try:
            self.file.close()
        except:
            pass

    def __next__(self):
        """Walk a chapter 10 file using python's iterator protocol and return
        a chapter10.packet.Packet object for each valid packet found.
        """

        while True:
            try:
                p = Packet(self.file, self.lazy)
                if p.check():
                    return p
            except (struct.error, EOFError):
                raise StopIteration
            except:
                pass
            self.file.seek(p.pos + 1)

    next = __next__

    def __repr__(self):
        return '<C10: {}>'.format(os.path.basename(self.file.name))

    def __iter__(self):
        return self
