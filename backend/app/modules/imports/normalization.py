from __future__ import annotations

import re
import unicodedata
from typing import Any

_WHITESPACE = re.compile(r"\s+")
_SYMBOL_WORDS = {
    "%": " percent ",
    "&": " and ",
    "+": " plus ",
    "@": " at ",
}


def normalize_header(value: Any) -> str:
    """Normalize a vendor header without relying on column position.

    Unicode compatibility forms are folded, formatting controls are discarded,
    punctuation/separators become spaces, and remaining text is case-folded.
    """

    if value is None:
        return ""

    normalized = unicodedata.normalize("NFKC", str(value)).casefold()
    characters: list[str] = []
    for character in normalized:
        if character in _SYMBOL_WORDS:
            characters.append(_SYMBOL_WORDS[character])
            continue
        category = unicodedata.category(character)
        if category == "Cf":
            continue
        if category.startswith(("P", "S", "Z")):
            characters.append(" ")
        else:
            characters.append(character)
    return _WHITESPACE.sub(" ", "".join(characters)).strip()
