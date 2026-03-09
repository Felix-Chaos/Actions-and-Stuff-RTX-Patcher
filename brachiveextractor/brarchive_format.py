# pylint: disable=missing-docstring, line-too-long, broad-exception-caught, too-many-locals, too-many-branches, too-many-statements, bare-except, too-few-public-methods, too-many-instance-attributes
import struct

MAGIC = 0x267052A0B125277D
VERSIONS = [1]
ENTRY_NAME_LEN_MAX = 247

class BrArchiveError(Exception):
    pass

class EntryDescriptor:
    def __init__(self, name: str, contents_offset: int, contents_len: int):
        self.name = name
        self.contents_offset = contents_offset
        self.contents_len = contents_len

    def __repr__(self):
        return f'<EntryDescriptor name="{self.name}" offset={self.contents_offset} len={self.contents_len}>'

def serialize(data_dict: dict) -> bytes:
    """
    Serializes a dictionary of {filename: content} into .brarchive bytes.
    content must be bytes or string (which will be utf-8 encoded).
    """
    header_fmt = '<QII' # uint64, uint32, uint32
    entries_count = len(data_dict)

    buf = bytearray()
    # Write header
    buf += struct.pack(header_fmt, MAGIC, entries_count, 1)

    descriptors = []
    current_offset = 0
    encoded_data = []

    for name, content in data_dict.items():
        if isinstance(content, str):
            content = content.encode('utf-8')

        content_len = len(content)
        encoded_data.append((name, content))

        descriptors.append(EntryDescriptor(name, current_offset, content_len))
        current_offset += content_len

    # Write entry descriptors
    for entry in descriptors:
        name_bytes = entry.name.encode('utf-8')
        if len(name_bytes) > ENTRY_NAME_LEN_MAX:
            raise BrArchiveError(f"Entry Name too long: {len(name_bytes)}")

        # 1 byte for name length
        buf.append(len(name_bytes))

        # pad name to ENTRY_NAME_LEN_MAX
        padded_name = name_bytes.ljust(ENTRY_NAME_LEN_MAX, b'\0')
        buf += padded_name

        # content offset (uint32) and len (uint32)
        buf += struct.pack('<II', entry.contents_offset, entry.contents_len)

    # Write contents
    for _, content in encoded_data:
        buf += content

    return bytes(buf)

def deserialize(data: bytes) -> dict:
    """
    Deserializes .brarchive bytes into a dictionary of {filename: content_bytes}.
    """
    if len(data) < 16:
        raise BrArchiveError("Data too short to contain header")

    header_fmt = '<QII'
    magic, entries, version = struct.unpack_from(header_fmt, data, 0)

    if magic != MAGIC:
        raise BrArchiveError(f"Magic Mismatch: expected {MAGIC}, got {magic}")

    if version not in VERSIONS:
        raise BrArchiveError(f"Unsupported Version: {version}")

    offset = 16
    descriptors = []

    for _ in range(entries):
        if offset >= len(data):
            raise BrArchiveError("Unexpected EOF while reading descriptors")

        name_len = data[offset]
        offset += 1

        if name_len > ENTRY_NAME_LEN_MAX:
            raise BrArchiveError(f"Entry Name too long in read: {name_len}")

        name_bytes = data[offset : offset + name_len]
        name = name_bytes.decode('utf-8')

        # Skip the rest of the 247 bytes padded array
        offset += ENTRY_NAME_LEN_MAX

        contents_offset, contents_len = struct.unpack_from('<II', data, offset)
        offset += 8

        descriptors.append(EntryDescriptor(name, contents_offset, contents_len))

    # Data contents start right after descriptors
    contents_start_offset = offset
    entry_map = {}

    for entry in descriptors:
        start = contents_start_offset + entry.contents_offset
        end = start + entry.contents_len

        if end > len(data):
            raise BrArchiveError(f"Offset out of bounds reading content for {entry.name}")

        entry_map[entry.name] = data[start:end]

    return entry_map
