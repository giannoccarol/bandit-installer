"""Android partition layout for phase 2, the same as the Lumia 950 XL installer.

The 950 XL installer (Android4Lumia950, branch cityman-temp, partition.sh) removes
Data, MainOS and MMOS with parted and then runs, for each Android partition,
`parted unit MiB mkpart <name> <end of last partition> <end + size>`. This module
computes the table parted produces from that sequence (checked against parted on a
disk image with the Lumia 1520's table, see tests/test_layout.py), writes it as raw
GPT sectors and checks the result with an independent reader:

- the new partitions start at the end of the last remaining partition (EFIESP on
  the 1520) and follow each other with exact MiB sizes;
- they take the lowest free entry slots, as parted does;
- parted's mkpart without a file system type gives the Linux filesystem type GUID
  and no attributes;
- userdata ("100%") ends at the last whole MiB before the last usable sector.

Every other GPT entry is kept byte for byte.
"""
import io
import struct
import uuid
import zlib

from . import gpt

MIB = 1024 * 1024
SECTORS_PER_MIB = MIB // gpt.SECTOR

# (name, size in MiB or None for the rest of the disk, file system), as in partition.sh
ANDROID_LAYOUT = (
    ("aboot", 1, "fat16"),
    ("boot", 34, "ext4"),
    ("recovery", 34, "ext4"),
    ("misc", 16, "ext4"),
    ("modem", 70, "fat16"),
    ("cache", 150, "ext4"),
    ("persist", 68, "ext4"),
    ("persistent", 68, "ext4"),
    ("fsc", 1, "ext4"),
    ("fsg", 2, "ext4"),
    ("metadata", 2, "ext4"),
    ("ssd", 2, "ext4"),
    ("modemst1", 2, "ext4"),
    ("modemst2", 2, "ext4"),
    ("vendor", 260, "ext4"),
    ("system", 3072, "ext4"),
    ("userdata", None, "ext4"),
)

# Windows partitions partition.sh deletes.
REMOVE = ("Data", "MainOS", "MMOS")

# Partitions that must survive unchanged: boot chain, firmware, calibration, unlock.
KEEP = ("DPP", "MODEM_FSG", "MODEM_FS1", "MODEM_FS2", "MODEM_FSC", "DDR", "SSD", "SBL1", "UEFI",
        "RPM", "TZ", "WINSECAPP", "TZAPPS", "PLAT", "EFIESP", "UEFI_BS_NV", "UEFI_RT_NV",
        "BACKUP_BS_NV", "DBI", "IS_UNLOCKED")

LINUX_FS_GUID = "0FC63DAF-8483-4772-8E79-3D69D8477DE4"


class LayoutError(Exception):
    pass


# ---------------------------------------------------------------------------
# raw GPT
# ---------------------------------------------------------------------------

class RawGpt:
    """The primary GPT as bytes: protective MBR, header fields and the entry array."""

    def __init__(self, mbr, header, entries, disk_sectors):
        self.mbr = mbr
        self.header = header            # the first header_size bytes of LBA 1
        self.entries = entries          # list of entry_size byte strings
        self.disk_sectors = disk_sectors
        (self.revision, self.header_size, _crc, _res, self.current_lba, self.backup_lba,
         self.first_usable, self.last_usable, self.disk_guid, self.entries_lba,
         self.n_entries, self.entry_size, _ecrc) = struct.unpack_from("<IIIIQQQQ16sQIII", header, 8)

    @classmethod
    def read(cls, f, disk_sectors):
        g = gpt.read_gpt(f)  # checks signature and both CRCs
        del g
        f.seek(0)
        mbr = f.read(gpt.SECTOR)
        f.seek(gpt.SECTOR)
        hdr = f.read(gpt.SECTOR)
        size = struct.unpack_from("<I", hdr, 12)[0]
        n, esize = struct.unpack_from("<II", hdr, 80)
        lba = struct.unpack_from("<Q", hdr, 72)[0]
        f.seek(lba * gpt.SECTOR)
        table = f.read(n * esize)
        raw = cls(mbr, hdr[:size], [table[i * esize:(i + 1) * esize] for i in range(n)], disk_sectors)
        if raw.current_lba != 1 or raw.backup_lba != disk_sectors - 1:
            raise LayoutError(f"GPT header does not match a disk of {disk_sectors} sectors "
                              f"(backup header at LBA {raw.backup_lba})")
        return raw

    def table_bytes(self):
        return b"".join(self.entries)

    def table_sectors(self):
        return (self.n_entries * self.entry_size + gpt.SECTOR - 1) // gpt.SECTOR

    def _header(self, current, backup, entries_lba):
        h = bytearray(self.header)
        struct.pack_into("<QQ", h, 24, current, backup)
        struct.pack_into("<Q", h, 72, entries_lba)
        struct.pack_into("<I", h, 88, zlib.crc32(self.table_bytes()) & 0xFFFFFFFF)
        struct.pack_into("<I", h, 16, 0)
        struct.pack_into("<I", h, 16, zlib.crc32(bytes(h)) & 0xFFFFFFFF)
        return bytes(h).ljust(gpt.SECTOR, b"\0")

    def primary(self):
        """LBA 0 .. 1 + table sectors: MBR, header, entries."""
        table = self.table_bytes().ljust(self.table_sectors() * gpt.SECTOR, b"\0")
        return self.mbr + self._header(1, self.disk_sectors - 1, 2) + table

    def backup_lba_start(self):
        return self.disk_sectors - 1 - self.table_sectors()

    def backup(self):
        """Entries then header, written from backup_lba_start() to the last sector."""
        table = self.table_bytes().ljust(self.table_sectors() * gpt.SECTOR, b"\0")
        start = self.backup_lba_start()
        return table + self._header(self.disk_sectors - 1, 1, start)


def entry_bytes(type_guid, part_guid, first, last, attrs, name, size=128):
    e = bytearray(size)
    e[0:16] = uuid.UUID(type_guid).bytes_le
    e[16:32] = uuid.UUID(part_guid).bytes_le
    struct.pack_into("<QQQ", e, 32, first, last, attrs)
    n = name.encode("utf-16le")
    if len(n) > 72:
        raise LayoutError(f"partition name too long: {name}")
    e[56:56 + len(n)] = n
    return bytes(e)


def _entry_info(e):
    if e[0:16] == b"\0" * 16:
        return None
    first, last, attrs = struct.unpack_from("<QQQ", e, 32)
    name = e[56:128].decode("utf-16le", "replace").split("\0", 1)[0]
    return {"name": name, "first": first, "last": last, "attrs": attrs,
            "type": str(uuid.UUID(bytes_le=bytes(e[0:16]))).upper()}


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------

class Plan:
    def __init__(self, before, after, removed, created):
        self.before = before        # RawGpt as read from the phone
        self.after = after          # RawGpt with the Android layout
        self.removed = removed      # [(slot, name, size)]
        self.created = created      # [(slot, name, first, last, fs)]

    def summary(self):
        out = []
        for slot, name, size in self.removed:
            out.append(f"- p{slot:<3} {name:<11} {size // MIB:>6} MiB")
        for slot, name, first, last, fs in self.created:
            size = (last - first + 1) * gpt.SECTOR
            out.append(f"+ p{slot:<3} {name:<11} {size // MIB:>6} MiB  {fs:<5} @ {first * gpt.SECTOR // MIB} MiB")
        return out


def make_plan(raw, guid_factory=None):
    """The table partition.sh leaves on this disk. Raises LayoutError when it does not apply."""
    guid_factory = guid_factory or (lambda: str(uuid.uuid4()).upper())
    entries = list(raw.entries)
    infos = [_entry_info(e) for e in entries]
    names = [i["name"] for i in infos if i]
    for name, _size, _fs in ANDROID_LAYOUT:
        if name in names:
            raise LayoutError(f"partition {name} already exists: the phone already has Android partitions")
    for name in KEEP:
        if names.count(name) > 1:
            raise LayoutError(f"partition {name} appears twice")
    missing = [n for n in ("EFIESP", "DPP", "MODEM_FS1", "MODEM_FS2", "MODEM_FSC", "MODEM_FSG", "SSD") if n not in names]
    if missing:
        raise LayoutError("partitions missing: " + ", ".join(missing))

    removed = []
    for slot, info in enumerate(infos, 1):
        if info and info["name"] in REMOVE:
            removed.append((slot, info["name"], (info["last"] - info["first"] + 1) * gpt.SECTOR))
            entries[slot - 1] = bytes(raw.entry_size)
            infos[slot - 1] = None
    if not removed:
        raise LayoutError("none of Data, MainOS, MMOS found")

    remaining = [i for i in infos if i]
    last = max(remaining, key=lambda i: i["first"])  # parted prints by start; partition.sh takes the last line
    if last["name"] != "EFIESP":
        raise LayoutError(f"the last partition on the disk is {last['name']}, not EFIESP: unexpected layout")
    end_mib = (last["last"] + 1) // SECTORS_PER_MIB
    if (last["last"] + 1) % SECTORS_PER_MIB:
        raise LayoutError(f"{last['name']} does not end on a MiB boundary")

    free_slots = [s for s, i in enumerate(infos, 1) if i is None]
    disk_end_mib = (raw.last_usable + 1) // SECTORS_PER_MIB
    created = []
    pos = end_mib
    for name, size, fs in ANDROID_LAYOUT:
        if not free_slots:
            raise LayoutError("no free GPT entry left")
        end = disk_end_mib if size is None else pos + size
        if end > disk_end_mib or end <= pos:
            raise LayoutError(f"{name} does not fit on the disk")
        first, last_s = pos * SECTORS_PER_MIB, end * SECTORS_PER_MIB - 1
        slot = free_slots.pop(0)
        entries[slot - 1] = entry_bytes(LINUX_FS_GUID, guid_factory(), first, last_s, 0, name, raw.entry_size)
        created.append((slot, name, first, last_s, fs))
        pos = end
    after = RawGpt(raw.mbr, raw.header, entries, raw.disk_sectors)
    return Plan(raw, after, removed, created)


# ---------------------------------------------------------------------------
# independent check
# ---------------------------------------------------------------------------

class _Regions(io.RawIOBase):
    """Read-only disk made of a few byte regions; zeros elsewhere."""

    def __init__(self, size, regions):
        self.size = size
        self.regions = regions      # [(offset, bytes)]
        self.pos = 0

    def readable(self):
        return True

    def seek(self, pos, whence=0):
        self.pos = pos if whence == 0 else self.pos + pos if whence == 1 else self.size + pos
        return self.pos

    def read(self, n=-1):
        n = self.size - self.pos if n < 0 else min(n, self.size - self.pos)
        out = bytearray(n)
        for off, data in self.regions:
            a, b = max(off, self.pos), min(off + len(data), self.pos + n)
            if a < b:
                out[a - self.pos:b - self.pos] = data[a - off:b - off]
        self.pos += n
        return bytes(out)


def verify(plan, primary=None, backup=None):
    """Checks the bytes about to be written (or read back) against the plan.

    Returns a list of problems; empty means the table is what partition.sh would leave.
    """
    primary = plan.after.primary() if primary is None else primary
    backup = plan.after.backup() if backup is None else backup
    raw = plan.before
    errors = []
    disk = _Regions(raw.disk_sectors * gpt.SECTOR,
                    [(0, primary), (plan.after.backup_lba_start() * gpt.SECTOR, backup)])
    try:
        new = gpt.read_gpt(disk)
    except gpt.GptError as e:
        return [f"new primary GPT unreadable: {e}"]
    if primary[:gpt.SECTOR] != raw.mbr:
        errors.append("protective MBR changed")

    # backup header and table
    disk.seek((raw.disk_sectors - 1) * gpt.SECTOR)
    bh = disk.read(gpt.SECTOR)
    if bh[:8] != b"EFI PART":
        errors.append("no backup GPT header")
    else:
        size = struct.unpack_from("<I", bh, 12)[0]
        h = bytearray(bh[:size])
        crc = struct.unpack_from("<I", h, 16)[0]
        struct.pack_into("<I", h, 16, 0)
        if zlib.crc32(bytes(h)) & 0xFFFFFFFF != crc:
            errors.append("backup GPT header CRC mismatch")
        cur, alt = struct.unpack_from("<QQ", bh, 24)
        if cur != raw.disk_sectors - 1 or alt != 1:
            errors.append("backup GPT header points to the wrong sectors")
        lba = struct.unpack_from("<Q", bh, 72)[0]
        disk.seek(lba * gpt.SECTOR)
        table = disk.read(raw.n_entries * raw.entry_size)
        if zlib.crc32(table) & 0xFFFFFFFF != struct.unpack_from("<I", bh, 88)[0]:
            errors.append("backup GPT table CRC mismatch")
        disk.seek(2 * gpt.SECTOR)
        if table != disk.read(raw.n_entries * raw.entry_size):
            errors.append("primary and backup tables differ")
        if bh[40:72] != primary[gpt.SECTOR + 40:gpt.SECTOR + 72]:
            errors.append("backup header geometry or disk GUID differs from the primary")

    # same header geometry as before
    if new.disk_guid != gpt._guid(raw.disk_guid):
        errors.append("disk GUID changed")
    if new.last_lba != raw.last_usable:
        errors.append("last usable LBA changed")

    # every entry not removed or created is unchanged, byte for byte
    disk.seek(2 * gpt.SECTOR)
    table = disk.read(raw.n_entries * raw.entry_size)
    new_entries = [table[i * raw.entry_size:(i + 1) * raw.entry_size] for i in range(raw.n_entries)]
    touched = {s for s, *_ in plan.removed} | {s for s, *_ in plan.created}
    for slot in range(1, raw.n_entries + 1):
        if slot not in touched and new_entries[slot - 1] != raw.entries[slot - 1]:
            errors.append(f"entry {slot} changed")
    for name in KEEP:
        a = [i for i in map(_entry_info, raw.entries) if i and i["name"] == name]
        b = [p for p in new.partitions if p.name == name]
        if len(a) != len(b) or (a and (a[0]["first"], a[0]["last"]) != (b[0].first, b[0].last)):
            errors.append(f"{name} moved or disappeared")

    # removed and created partitions
    names = [p.name for p in new.partitions]
    for name in REMOVE:
        if name in names:
            errors.append(f"{name} still present")
    order = [n for n, _s, _f in ANDROID_LAYOUT]
    created = sorted((p for p in new.partitions if p.name in order), key=lambda p: p.first)
    if [p.name for p in created] != order:
        errors.append("Android partitions missing, repeated or out of order: " + ", ".join(p.name for p in created))
    else:
        efiesp = new.by_name("EFIESP")
        pos = efiesp.last + 1
        for p, (name, size, _fs) in zip(created, ANDROID_LAYOUT):
            if p.first != pos:
                errors.append(f"{name} does not start right after the previous partition")
            if p.first % SECTORS_PER_MIB:
                errors.append(f"{name} is not MiB aligned")
            if size is not None and p.size != size * MIB:
                errors.append(f"{name}: {p.size} bytes instead of {size} MiB")
            if p.type_guid != LINUX_FS_GUID or p.attrs:
                errors.append(f"{name}: unexpected type or attributes")
            pos = p.last + 1
        last = created[-1]
        if last.last > raw.last_usable or (raw.last_usable + 1) - (last.last + 1) >= SECTORS_PER_MIB:
            errors.append("userdata does not end at the last whole MiB of the disk")

    # no overlaps, everything inside the usable area
    spans = sorted((p.first, p.last, p.name) for p in new.partitions)
    for (a1, b1, n1), (a2, b2, n2) in zip(spans, spans[1:]):
        if a2 <= b1:
            errors.append(f"{n1} and {n2} overlap")
    for p in new.partitions:
        if p.first < raw.first_usable or p.last > raw.last_usable:
            errors.append(f"{p.name} outside the usable area")
    return errors
