from functools import lru_cache
import unicodedata

_Cf_Zp_Zl_SET = {
    0x0000,
    0x2028, 0x2029, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
    0x2060, 0x2061, 0x2062, 0x2063,
    0x200B, 0x200C, 0x200D, 0x200E, 0x200F,
}

_COMBINING_CATEGORIES = {"Me", "Mn"}

_EAWIDE = {"F", "W"}


@lru_cache(100)
def wcwidth(c: str) -> int:
    """Determine how many columns are needed to display a character in a terminal.

    Returns -1 if the character is not printable.
    Returns 0, 1 or 2 for other characters.
    """
    o = ord(c)

    # ASCII fast path.
    if 0x20 <= o < 0x07F:
        return 1

    # Some Cf/Zp/Zl characters which should be zero-width.
    if o in _Cf_Zp_Zl_SET:
        return 0

    category = unicodedata.category(c)

    # Control characters.
    if category == "Cc":
        return -1

    # Combining characters with zero width.
    if category in _COMBINING_CATEGORIES:
        return 0

    # Full/Wide east asian characters.
    if unicodedata.east_asian_width(c) in _EAWIDE:
        return 2

    return 1


def wcswidth(s: str) -> int:
    """Determine how many columns are needed to display a string in a terminal.

    Returns -1 if the string contains non-printable characters.
    """
    width = 0
    for c in unicodedata.normalize("NFC", s):
        wc = wcwidth(c)
        if wc < 0:
            return -1
        width += wc
    return width
