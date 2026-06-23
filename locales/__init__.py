"""Locales package — load locale strings by language code."""

from typing import Dict

from locales.en import STRINGS as EN_STRINGS
from locales.uk import STRINGS as UK_STRINGS

_LOCALES: Dict[str, Dict[str, str]] = {
    "en": EN_STRINGS,
    "uk": UK_STRINGS,
}


def get_strings(lang: str = "en") -> Dict[str, str]:
    """Return localization strings for the given language code."""
    return _LOCALES.get(lang, EN_STRINGS)
