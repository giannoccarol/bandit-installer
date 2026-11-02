"""Small FAT12/16 reader and formatter.

Reader: files from the phone's DPP partition (QCOM/WLAN.PROVISION, QCOM/BT.PROVISION:
long names). Formatter: the FAT file systems partition.sh makes with mkfs.fat on
aboot and modem, built on the PC because the recovery has no mkfs.fat; the aboot one
also gets lk1st (emmc_appsboot.mbn), as use_aboot() does on the 950 XL.
"""
import struct
import time

SECTOR = 512


class FatError(Exception):
    pass


# ---------------------------------------------------------------------------
# reader
# ---------------------------------------------------------------------------

class FatImage:
    def __init__(self, data):
        self.d = data
        if len(data) < SECTOR or data[510:512] != b"\x55\xaa":
            raise FatError("no FAT boot sector")
        (self.bps, self.spc, self.reserved, self.nfats, self.root_entries, tot16, _media,
         self.fatsz, _spt, _heads, _hidden, tot32) = struct.unpack_from("<HBHBHHBHHHII", data, 11)
        if self.bps != SECTOR or not self.spc or not self.fatsz:
            raise FatError("unsupported FAT geometry (FAT32 or not FAT)")
        self.total = tot16 or tot32
        self.root_start = self.reserved + self.nfats * self.fatsz
        self.root_sectors = (self.root_entries * 32 + SECTOR - 1) // SECTOR
        self.data_start = self.root_start + self.root_sectors
        self.clusters = (self.total - self.data_start) // self.spc
        self.fat12 = self.clusters < 4085
        self.fat = data[self.reserved * SECTOR:(self.reserved + self.fatsz) * SECTOR]

    def _next(self, c):
        if self.fat12:
            v = struct.unpack_from("<H", self.fat, c + c // 2)[0]
            v = v >> 4 if c & 1 else v & 0xFFF
            return None if v >= 0xFF8 else v
        v = struct.unpack_from("<H", self.fat, c * 2)[0]
        return None if v >= 0xFFF8 else v

    def _chain(self, c, size=None):
        out, seen = bytearray(), set()
        while c is not None and c >= 2:
            if c in seen or c >= self.clusters + 2:
                raise FatError("broken cluster chain")
            seen.add(c)
            off = (self.data_start + (c - 2) * self.spc) * SECTOR
            out += self.d[off:off + self.spc * SECTOR]
            c = self._next(c)
        return bytes(out if size is None else out[:size])

    def _entries(self, raw):
        lfn = []
        for i in range(0, len(raw), 32):
            e = raw[i:i + 32]
            if e[0] == 0:
                break
            if e[0] == 0xE5:
                lfn = []
                continue
            if e[11] == 0x0F:
                lfn.insert(0, e[1:11] + e[14:26] + e[28:32])
                continue
            if e[11] & 0x08:  # volume label
                lfn = []
                continue
            short = e[0:8].decode("ascii", "replace").rstrip()
            ext = e[8:11].decode("ascii", "replace").rstrip()
            name = short + ("." + ext if ext else "")
            if lfn:
                name = b"".join(lfn).decode("utf-16le", "replace").split("\0", 1)[0]
            lfn = []
            cluster = struct.unpack_from("<H", e, 26)[0]
            size = struct.unpack_from("<I", e, 28)[0]
            yield name, bool(e[11] & 0x10), cluster, size

    def read(self, path):
        """Contents of a file, path like 'QCOM/WLAN.PROVISION' (case-insensitive)."""
        parts = [p for p in path.replace("\\", "/").split("/") if p]
        raw = self.d[self.root_start * SECTOR:self.data_start * SECTOR]
        for i, part in enumerate(parts):
            for name, is_dir, cluster, size in self._entries(raw):
                if name.upper() == part.upper():
                    if i == len(parts) - 1:
                        if is_dir:
                            raise FatError(f"{path} is a folder")
                        return self._chain(cluster, size) if size else b""
                    if not is_dir:
                        raise FatError(f"{part} is not a folder")
                    raw = self._chain(cluster)
                    break
            else:
                raise FatError(f"{path} not found")
        raise FatError(f"{path} not found")


# ---------------------------------------------------------------------------
# formatter
# ---------------------------------------------------------------------------

def _short_name(name, n):
    base = "".join(c for c in name.upper() if c.isalnum())[:6] or "FILE"
    ext = name.rsplit(".", 1)[1].upper()[:3] if "." in name else ""
    return (f"{base}~{n}".ljust(8) + ext.ljust(3)).encode("ascii")


def _lfn_entries(name, short):
    csum = 0
    for b in short:
        csum = (((csum & 1) << 7) + (csum >> 1) + b) & 0xFF
    u = name.encode("utf-16le")
    if len(name) % 13:
        u += b"\0\0"
        u += b"\xff" * ((-len(u)) % 26)
    chunks = [u[i:i + 26] for i in range(0, len(u), 26)]
    out = []
    for i, c in enumerate(chunks, 1):
        e = bytearray(32)
        e[0] = i | (0x40 if i == len(chunks) else 0)
        e[1:11], e[11], e[13] = c[0:10], 0x0F, csum
        e[14:26], e[28:32] = c[10:22], c[22:26]
        out.append(bytes(e))
    return list(reversed(out))


def make_fat(size, files=None, label="NO NAME", volume_id=None, when=None):
    """A FAT12 or FAT16 image of exactly `size` bytes with files in the root folder."""
    files = files or {}
    total = size // SECTOR
    if total < 64:
        raise FatError("too small for FAT")
    for spc in (1, 2, 4, 8, 16, 32, 64):
        reserved, nfats, root_entries = 1, 2, 512
        root_sectors = root_entries * 32 // SECTOR
        # FAT size: iterate, because it depends on the cluster count
        fatsz = 1
        while True:
            clusters = (total - reserved - nfats * fatsz - root_sectors) // spc
            fat12 = clusters < 4085
            need = ((clusters + 2) * 3 + 1) // 2 if fat12 else (clusters + 2) * 2
            need = (need + SECTOR - 1) // SECTOR
            if need <= fatsz:
                break
            fatsz = need
        if clusters < 65525:
            break
    else:
        raise FatError("too large for FAT16")
    img = bytearray(total * SECTOR)
    vid = volume_id if volume_id is not None else int(time.time()) & 0xFFFFFFFF
    bs = bytearray(SECTOR)
    bs[0:3] = b"\xeb\x3c\x90"
    bs[3:11] = b"mkfs.fat"
    struct.pack_into("<HBHBHHBHHHII", bs, 11, SECTOR, spc, reserved, nfats, root_entries,
                     total if total < 65536 else 0, 0xF8, fatsz, 32, 64, 0, total if total >= 65536 else 0)
    struct.pack_into("<BBBI", bs, 36, 0x80, 0, 0x29, vid)
    bs[43:54] = label.upper().encode("ascii")[:11].ljust(11)
    bs[54:62] = (b"FAT12   " if fat12 else b"FAT16   ")
    bs[510:512] = b"\x55\xaa"
    img[0:SECTOR] = bs

    fat = bytearray(fatsz * SECTOR)

    def set_fat(c, v):
        if fat12:
            o = c + c // 2
            cur = struct.unpack_from("<H", fat, o)[0]
            cur = (cur & 0x000F) | (v << 4) if c & 1 else (cur & 0xF000) | v
            struct.pack_into("<H", fat, o, cur & 0xFFFF)
        else:
            struct.pack_into("<H", fat, c * 2, v)

    eoc = 0xFFF if fat12 else 0xFFFF
    set_fat(0, (0xF00 if fat12 else 0xFF00) | 0xF8)
    set_fat(1, eoc)
    root = bytearray()
    lab = bytearray(32)
    lab[0:11] = label.upper().encode("ascii")[:11].ljust(11)
    lab[11] = 0x08
    root += lab
    t = time.localtime(when if when is not None else time.time())
    ftime = (t.tm_hour << 11) | (t.tm_min << 5) | (t.tm_sec // 2)
    fdate = ((t.tm_year - 1980) << 9) | (t.tm_mon << 5) | t.tm_mday
    data_start = reserved + nfats * fatsz + root_sectors
    cluster_bytes = spc * SECTOR
    nxt = 2
    for n, (name, data) in enumerate(sorted(files.items()), 1):
        short = _short_name(name, n)
        for e in _lfn_entries(name, short):
            root += e
        count = (len(data) + cluster_bytes - 1) // cluster_bytes
        if nxt + count > clusters + 2:
            raise FatError(f"{name} does not fit")
        first = nxt if count else 0
        for i in range(count):
            set_fat(nxt + i, nxt + i + 1 if i < count - 1 else eoc)
            off = (data_start + (nxt + i - 2) * spc) * SECTOR
            chunk = data[i * cluster_bytes:(i + 1) * cluster_bytes]
            img[off:off + len(chunk)] = chunk
        nxt += count
        e = bytearray(32)
        e[0:11] = short
        e[11] = 0x20
        struct.pack_into("<HHHHHHHI", e, 14, ftime, fdate, fdate, 0, ftime, fdate, first, len(data))
        root += e
    if len(root) > root_entries * 32:
        raise FatError("too many files")
    for i in range(nfats):
        off = (reserved + i * fatsz) * SECTOR
        img[off:off + len(fat)] = fat
    off = (reserved + nfats * fatsz) * SECTOR
    img[off:off + len(root)] = root
    return bytes(img)
