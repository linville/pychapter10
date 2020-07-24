
from io import BytesIO
from array import array

from .util import compile_fmt


class InvalidPacket(Exception):
    pass


class Packet(object):
    """Reads header and associates a datatype specific object."""

    FORMAT = compile_fmt('''
        u16 sync_pattern
        u16 channel_id
        u32 packet_length
        u32 data_length
        u8 header_version
        u8 sequence_number
        u1 secondary_header
        u1 ipts_source
        u1 rtc_sync_error
        u1 data_overflow_error
        u2 secondary_format
        u2 data_checksum_present
        u8 data_type
        u48 rtc
        u16 header_checksum''')

    SECONDARY_FORMAT = compile_fmt('''
        u64 secondary_time
        p16 reserved
        u16 secondary_checksum''')

    csdw_format = None
    data_format = None
    # TODO: rename to message label & format?
    iph_format = None
    item_label = None

    def __init__(self, file):
        """Takes an open file object with its cursor at this packet."""

        # Read the packet header and save header sums for later.
        header = file.read(24)
        self.header_sums = sum(array('H', header)[:-1]) & 0xffff

        # Parse header fields into attributes.
        self.__dict__.update(self.FORMAT.unpack(header).items())

        # Read the secondary header (if any).
        self.time = None
        secondary = bytes()
        if self.secondary_header:
            secondary = file.read(12)
            self.secondary_sums = sum(array('H', secondary)[:-1]) & 0xffff
            self.__dict__.update(self.SECONDARY_FORMAT.unpack(file.read(12)))

        header_size = len(header + secondary)
        body = file.read(self.packet_length - header_size)
        self.file = BytesIO(header + secondary + body)
        self.file.seek(header_size)

        error = self.get_errors()
        if error:
            raise error

        from .datatypes import format
        self.type, self._format = format(self.data_type)
        self.parse()

    def parse(self):
        """Seek to packet body, call type-specific parsing, and return file
        to its previous index.
        """

        self.parse_csdw()
        self.parse_data()

    def parse_csdw(self):
        if self.csdw_format:
            self.__dict__.update(self.csdw_format.unpack(
                self.file.read(4)))

    def parse_data(self):
        self.all = []
        if not self.iph_format:
            data_len = self.packet_length - (
                self.secondary_header and 36 or 24)
            self.data = self.file.read(data_len - 4)
            if self.data_format is not None:
                raw = self.data[:self.data_format.calcsize()]
                self.__dict__.update(self.data_format.unpack(raw))
        else:
            end = self.file.tell() - 4 + self.data_length
            while True:
                length = getattr(self, 'item_size', 0)

                iph_size = self.iph_format.calcsize() // 8
                raw = self.file.read(iph_size)
                iph = self.iph_format.unpack(raw)

                if 'length' in iph:
                    length = iph['length']

                data = self.file.read(length)
                self.all.append(Item(data, self.item_label, self.iph_format,
                                     **iph))

                # Account for filler byte when length is odd.
                if length % 2:
                    self.file.seek(1, 1)

                if getattr(self, 'count', None) and len(self) == self.count:
                    break

                if self.file.tell() >= end:
                    break

    @classmethod
    def from_string(cls, s):
        """Create a packet object from a string."""

        return cls(BytesIO(s))

    def get_errors(self):
        """Validate the packet using checksums and verifying fields."""

        if self.sync_pattern != 0xeb25:
            return InvalidPacket('Incorrect sync pattern!')
        elif self.header_sums != self.header_checksum:
            return InvalidPacket('Header checksum mismatch!')
        elif self.secondary_header:
            if self.secondary_sums != self.secondary_checksum:
                return InvalidPacket('Secondary header checksum mismatch!')
        elif self.data_length > 524288:
            return InvalidPacket('Data length larger than allowed!')

    def check(self):
        return self.get_errors() is None

    # TODO: switch to a generator instead of building .all immediately?
    def __iter__(self):
        return iter(self.all)

    def __len__(self):
        return len(self.all)

    def __bytes__(self):
        """Returns the entire packet as raw bytes."""

        self.file.seek(0)
        return self.file.read()

    __str__ = __bytes__

    def __repr__(self):
        return '<C10 Packet {} {} bytes>'.format(self.data_type,
                                                 len(bytes(self)))

    def __setstate__(self, state):
        state['file'] = BytesIO(state['file'])
        self.__dict__.update(state)

    def __getstate__(self):
        state = self.__dict__.copy()
        state['file'] = bytes(self)
        for k, v in list(state.items()):
            if callable(v):
                del state[k]
        return state


class Item(object):
    """The base container for packet data."""

    def __init__(self, data, label="Packet Data", item_format=None, **kwargs):
        self.__dict__.update(kwargs)
        self.item_format = item_format
        self.data, self.label = data, label

    def __repr__(self):
        return '<%s>' % (self.label)

    def bytes(self):
        return self.data

    def __bytes__(self):
        return self.pack()

    def __str__(self):
        return str(self.pack())

    def pack(self, format=None):
        """Return bytes() containing the item's IPH and data."""

        if format is None:
            format = self.item_format
        return format.pack(self.__dict__)
