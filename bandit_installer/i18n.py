"""Two languages: English (default) and Italian, written side by side in the code.

L("testo", "text") returns the string for the current language.
"""
import os

_lang = "en"


def detect():
    """English by default; Italian only when asked (--lang it, BANDIT_LANG=it or the settings page)."""
    env = (os.environ.get("BANDIT_LANG") or "").lower()
    return "it" if env.startswith("it") else "en"


def set_lang(lang):
    global _lang
    _lang = "it" if lang == "it" else "en"


def get_lang():
    return _lang


def L(it, en):
    return it if _lang == "it" else en
