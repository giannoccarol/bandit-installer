"""Two languages, Italian and English, written side by side in the code.

L("testo", "text") returns the string for the current language.
"""
import locale
import os

_lang = "en"


def detect():
    env = os.environ.get("BANDIT_LANG") or os.environ.get("LC_ALL") or os.environ.get("LANG") or ""
    if env.lower().startswith("it"):
        return "it"
    if env.lower().startswith("en"):
        return "en"
    if os.name == "nt":
        try:
            import ctypes
            if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x10:
                return "it"
        except Exception:
            pass
    try:
        loc = locale.getlocale()[0] or ""
    except Exception:
        loc = ""
    return "it" if loc.lower().startswith("it") else "en"


def set_lang(lang):
    global _lang
    _lang = "it" if lang == "it" else "en"


def get_lang():
    return _lang


def L(it, en):
    return it if _lang == "it" else en
