"""Minimal read-only parser for Windows registry hives (regf).

Used to read the phone's BCD (a registry hive) on both Windows and Linux,
so the same checks run before and after every change, whatever tool wrote
the file (hivex on Linux, bcdedit on Windows).
"""
import struct


class HiveError(Exception):
    pass


class Key:
    __slots__ = ("hive", "off", "name")

    def __init__(self, hive, off, name):
        self.hive = hive
        self.off = off
        self.name = name

    def subkeys(self):
        return self.hive._subkeys(self.off)

    def subkey(self, name):
        low = name.lower()
        for k in self.subkeys():
            if k.name.lower() == low:
                return k
        return None

    def path(self, *names):
        k = self
        for n in names:
            k = k.subkey(n) if k else None
        return k

    def values(self):
        """Returns {name_lower: (type, bytes)}."""
        return self.hive._values(self.off)

    def value(self, name):
        return self.values().get(name.lower())


class Hive:
    def __init__(self, data):
        if len(data) < 0x1000 or data[:4] != b"regf":
            raise HiveError("not a registry hive")
        self.data = data
        self.minor = struct.unpack_from("<I", data, 0x18)[0]
        root = struct.unpack_from("<I", data, 0x24)[0]
        self.root = Key(self, root, self._nk_name(root))

    @classmethod
    def open(cls, path):
        with open(path, "rb") as f:
            return cls(f.read())

    # cells ---------------------------------------------------------------
    def _cell(self, off):
        pos = 0x1000 + off
        if off in (0xFFFFFFFF, 0) or pos + 4 > len(self.data):
            raise HiveError(f"bad cell offset 0x{off:x}")
        size = struct.unpack_from("<i", self.data, pos)[0]
        if size >= 0:
            raise HiveError(f"cell 0x{off:x} is free")
        size = -size
        if pos + size > len(self.data):
            raise HiveError(f"cell 0x{off:x} runs past the end of the hive")
        return self.data[pos + 4:pos + size]

    def _nk(self, off):
        c = self._cell(off)
        if c[:2] != b"nk":
            raise HiveError(f"expected nk at 0x{off:x}")
        return c

    def _nk_name(self, off):
        c = self._nk(off)
        flags = struct.unpack_from("<H", c, 2)[0]
        nlen = struct.unpack_from("<H", c, 72)[0]
        raw = c[76:76 + nlen]
        return raw.decode("latin-1") if flags & 0x20 else raw.decode("utf-16le")

    def _list_offsets(self, off, depth=0):
        if depth > 4:
            raise HiveError("subkey index too deep")
        c = self._cell(off)
        sig = c[:2]
        n = struct.unpack_from("<H", c, 2)[0]
        if sig in (b"lf", b"lh"):
            return [struct.unpack_from("<I", c, 4 + 8 * i)[0] for i in range(n)]
        if sig == b"li":
            return [struct.unpack_from("<I", c, 4 + 4 * i)[0] for i in range(n)]
        if sig == b"ri":
            out = []
            for i in range(n):
                out += self._list_offsets(struct.unpack_from("<I", c, 4 + 4 * i)[0], depth + 1)
            return out
        raise HiveError(f"unknown subkey list {sig!r}")

    def _subkeys(self, off):
        c = self._nk(off)
        n, lst = struct.unpack_from("<II", c, 20)[0], struct.unpack_from("<I", c, 28)[0]
        if n == 0 or lst == 0xFFFFFFFF:
            return []
        return [Key(self, o, self._nk_name(o)) for o in self._list_offsets(lst)]

    def _data(self, size, doff):
        if size & 0x80000000:
            size &= 0x7FFFFFFF
            return struct.pack("<I", doff)[:size]
        if size == 0:
            return b""
        c = self._cell(doff)
        if size > 16344 and self.minor >= 4 and c[:2] == b"db":
            nseg, segs = struct.unpack_from("<HI", c, 2)
            segc = self._cell(segs)
            out = b""
            for i in range(nseg):
                out += self._cell(struct.unpack_from("<I", segc, 4 * i)[0])[:16344]
            return out[:size]
        return c[:size]

    def _values(self, off):
        c = self._nk(off)
        n, lst = struct.unpack_from("<I", c, 36)[0], struct.unpack_from("<I", c, 40)[0]
        out = {}
        if n == 0 or lst == 0xFFFFFFFF:
            return out
        vl = self._cell(lst)
        for i in range(n):
            vo = struct.unpack_from("<I", vl, 4 * i)[0]
            v = self._cell(vo)
            if v[:2] != b"vk":
                raise HiveError(f"expected vk at 0x{vo:x}")
            nlen, dsize, doff, vtype, flags = struct.unpack_from("<HIIIH", v, 2)
            raw = v[20:20 + nlen]
            name = raw.decode("latin-1") if flags & 1 else raw.decode("utf-16le")
            out[name.lower()] = (vtype, self._data(dsize, doff))
        return out
