"""What mode the phone is in, and fastboot/adb.

The mode comes from the USB ids (cheap, works without drivers) and, for
fastboot and adb, from the tools themselves.
"""
import re
import threading
import time

from . import sysdeps
from .i18n import L

# (vid, pid) -> mode
USB_MODES = {
    ("045e", "9006"): "mass",       # WPinternals mass storage ("Phone MMC Stor")
    ("0421", "0714"): "bootmgr",    # Windows Phone boot manager starting
    ("0421", "066e"): "flash",      # UEFI flash mode (volume up)
    ("0421", "0661"): "windows",    # Windows Phone running
    ("18d1", "d00d"): "fastboot",   # lk1st / any fastboot
    ("18d1", "d00e"): "k1",         # K1 test kernel (CDC-ACM serial)
    ("05c6", "9008"): "edl",        # Qualcomm emergency download
}


def mode_text(mode):
    return {
        "none": L("non collegato", "not connected"),
        "mass": L("mass storage (WPinternals)", "mass storage (WPinternals)"),
        "bootmgr": L("boot manager di Windows Phone", "Windows Phone boot manager"),
        "flash": L("modalità flash (volume su)", "flash mode (volume up)"),
        "windows": L("Windows Phone avviato", "Windows Phone running"),
        "fastboot": L("fastboot", "fastboot"),
        "k1": L("kernel di prova K1 (seriale USB)", "K1 test kernel (USB serial)"),
        "edl": L("Qualcomm 9008 (emergenza)", "Qualcomm 9008 (emergency)"),
        "adb": L("Android (adb)", "Android (adb)"),
        "recovery": L("recovery (adb)", "recovery (adb)"),
        "sideload": L("recovery, sideload", "recovery, sideload"),
        "unauthorized": L("Android, adb non autorizzato", "Android, adb not authorised"),
        "android": L("Android (senza adb)", "Android (no adb)"),
    }.get(mode, mode)


class Snapshot:
    def __init__(self, mode="none", detail="", usb=None, problem="", when=None):
        self.mode = mode
        self.detail = detail
        self.usb = usb or []
        self.problem = problem      # e.g. Windows driver missing
        self.when = when or time.time()

    def text(self):
        t = mode_text(self.mode)
        if self.detail:
            t += f" — {self.detail}"
        return t


class Phone:
    def __init__(self, system, log):
        self.system = system
        self.log = log
        self.fastboot_exe = system.find_tool("fastboot")
        self.adb_exe = system.find_tool("adb")

    def refresh_tools(self):
        self.fastboot_exe = self.system.find_tool("fastboot")
        self.adb_exe = self.system.find_tool("adb")

    # tools -----------------------------------------------------------------
    def fastboot(self, args, timeout=60, quiet=False):
        if not self.fastboot_exe:
            return 127, "fastboot not found"
        rc, out = sysdeps.run([self.fastboot_exe] + args, timeout=timeout)
        if not quiet:
            self.log(f"$ fastboot {' '.join(args)}  (rc={rc})\n{out.rstrip()}")
        return rc, out

    def adb(self, args, timeout=60, quiet=False):
        if not self.adb_exe:
            return 127, "adb not found"
        rc, out = sysdeps.run([self.adb_exe] + args, timeout=timeout)
        if not quiet:
            self.log(f"$ adb {' '.join(args)}  (rc={rc})\n{out.rstrip()}")
        return rc, out

    def fastboot_serials(self):
        rc, out = self.fastboot(["devices"], timeout=10, quiet=True)
        return [l.split()[0] for l in out.splitlines() if l.strip().endswith("fastboot")]

    def adb_states(self):
        rc, out = self.adb(["devices"], timeout=10, quiet=True)
        states = []
        for l in out.splitlines()[1:]:
            parts = l.split()
            if len(parts) >= 2:
                states.append(parts[1])
        return states

    def getvar(self, name):
        rc, out = self.fastboot(["getvar", name], timeout=15, quiet=True)
        m = re.search(rf"^{re.escape(name)}:\s*(.*)$", out, re.M)
        return m.group(1).strip() if m else None

    # mode ------------------------------------------------------------------
    def snapshot(self, use_tools=True):
        usb = self.system.usb_devices()
        modes = []
        problem = ""
        for d in usb:
            m = USB_MODES.get((d.vid, d.pid))
            if m:
                modes.append((m, d))
                if d.status and d.status not in ("OK", "Unknown") and sysdeps.IS_WINDOWS:
                    problem = L(f"Windows segnala {d.status} per {d.id}: driver mancante?",
                                f"Windows reports {d.status} for {d.id}: missing driver?")
        names = [m for m, _ in modes]
        if use_tools and ("fastboot" in names or not names):
            serials = self.fastboot_serials() if self.fastboot_exe else []
            if serials:
                product = self.getvar("product") or "?"
                return Snapshot("fastboot", product, usb, problem)
        if use_tools and self.adb_exe and not set(names) & {"mass", "fastboot", "edl", "bootmgr", "flash"}:
            st = self.adb_states()
            for s in st:
                if s in ("device",):
                    return Snapshot("adb", "", usb, problem)
                if s in ("recovery", "sideload", "unauthorized"):
                    return Snapshot(s, "", usb, problem)
        for pref in ("edl", "mass", "fastboot", "k1", "flash", "bootmgr", "windows"):
            if pref in names:
                return Snapshot(pref, "", usb, problem)
        if any(d.vid == "18d1" for d in usb):
            return Snapshot("android", "", usb, problem)
        return Snapshot("none", "", usb, problem)


class Poller:
    """Refreshes the phone mode in the background while menus wait for keys.

    Paused during operations: a background `fastboot devices` must never run
    while a transfer is in progress.
    """

    def __init__(self, phone, interval):
        self.phone = phone
        self.interval = interval
        self.snap = Snapshot()
        self.version = 0
        self._active = False
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while True:
            self._wake.wait(self.interval)
            self._wake.clear()
            with self._lock:
                if not self._active:
                    continue
                try:
                    s = self.phone.snapshot()
                except Exception as e:  # never kill the UI thread
                    s = Snapshot("none", f"error: {e}")
            if s.mode != self.snap.mode or s.detail != self.snap.detail or s.problem != self.snap.problem:
                self.version += 1
            self.snap = s

    def start(self):
        self._active = True
        self._wake.set()

    def stop(self):
        """Stops polling and waits for a running poll to finish."""
        self._active = False
        with self._lock:
            pass

    def now(self):
        """Fresh snapshot taken in the foreground."""
        self.stop()
        self.snap = self.phone.snapshot()
        self.version += 1
        return self.snap
