"""Read-only GPT parser.

Works on any binary file object (a Linux block device, a Windows
\\\\.\\PhysicalDriveN handle or a disk image), so both platforms find the
phone's partitions the same way.
"""
import struct
import uuid
import zlib

SECTOR = 512

# Partitions that must exist on a Lumia in mass storage mode.
LUMIA_REQUIRED = ("EFIESP", "MainOS", "PLAT", "DPP")

# GPT attribute bit 63: Windows assigns no drive letter.
ATTR_NO_DRIVE_LETTER = 1 << 63


class GptError(Exception):
    pass


class Partition:
    def __init__(self, index, name, type_guid, part_guid, first, last, attrs):
        self.index = index          # 1-based slot number (Linux /dev/sdX<index>)
        self.name = name
        self.type_guid = type_guid
        self.part_guid = part_guid
        self.first = first
        self.last = last
        self.attrs = attrs

    @property
    def offset(self):
        return self.first * SECTOR

    @property
    def size(self):
        return (self.last - self.first + 1) * SECTOR

    def __repr__(self):
        return f"<Partition {self.index} {self.name} @{self.first} {self.size}>"


class Gpt:
    def __init__(self, disk_guid, partitions, last_lba, entries_crc_ok=True):
        self.disk_guid = disk_guid
        self.partitions = partitions
        self.last_lba = last_lba
        self.entries_crc_ok = entries_crc_ok

    def by_name(self, name):
        for p in self.partitions:
            if p.name == name:
                return p
        return None

    def names(self):
        return [p.name for p in self.partitions]

    def looks_like_lumia(self):
        names = set(self.names())
        return all(n in names for n in LUMIA_REQUIRED)

    def has_android(self):
        names = set(self.names())
        return {"boot", "system"} <= names


def _read_at(f, offset, size):
    f.seek(offset)
    data = b""
    while len(data) < size:
        chunk = f.read(size - len(data))
        if not chunk:
            break
        data += chunk
    return data


def _guid(raw):
    return str(uuid.UUID(bytes_le=raw)).upper()


def read_gpt(f):
    """Parses the primary GPT from file object f (must be opened in binary mode).

    Reads are sector aligned, as Windows raw disk handles require.
    """
    hdr = _read_at(f, SECTOR, SECTOR)
    if len(hdr) < 92 or hdr[:8] != b"EFI PART":
        raise GptError("no GPT header at LBA 1")
    (rev, hsize, hcrc, _res, cur_lba, backup_lba, first_usable, last_usable,
     disk_guid, entries_lba, n_entries, entry_size, entries_crc) = struct.unpack_from(
        "<IIIIQQQQ16sQIII", hdr, 8)
    if hsize < 92 or hsize > SECTOR:
        raise GptError(f"bad GPT header size {hsize}")
    check = bytearray(hdr[:hsize])
    check[16:20] = b"\0\0\0\0"
    if zlib.crc32(bytes(check)) & 0xFFFFFFFF != hcrc:
        raise GptError("GPT header CRC mismatch")
    if entry_size < 128 or n_entries > 1024:
        raise GptError("unexpected GPT entry table")
    table_len = n_entries * entry_size
    table_len_aligned = (table_len + SECTOR - 1) // SECTOR * SECTOR
    table = _read_at(f, entries_lba * SECTOR, table_len_aligned)[:table_len]
    crc_ok = zlib.crc32(table) & 0xFFFFFFFF == entries_crc
    parts = []
    for i in range(n_entries):
        e = table[i * entry_size:(i + 1) * entry_size]
        if len(e) < 128:
            break
        tg = e[0:16]
        if tg == b"\0" * 16:
            continue
        first, last, attrs = struct.unpack_from("<QQQ", e, 32)
        name = e[56:128].decode("utf-16le", "replace").split("\0", 1)[0]
        parts.append(Partition(i + 1, name, _guid(tg), _guid(e[16:32]), first, last, attrs))
    if not crc_ok:
        raise GptError("GPT partition table CRC mismatch")
    return Gpt(_guid(disk_guid), parts, last_usable, crc_ok)
