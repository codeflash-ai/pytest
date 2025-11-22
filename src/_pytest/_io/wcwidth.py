from functools import lru_cache
import unicodedata


_EAW_CACHE = {"F", "W"}

_ucd_category = unicodedata.category

_ucd_eaw = unicodedata.east_asian_width

_ucd_normalize = unicodedata.normalize

_ZERO_WIDTH_CODES = (
    {0x0000}
    | set(range(0x200B, 0x2010))  # [0x200B, 0x200F]
    | set(range(0x2028, 0x202F))  # [0x2028, 0x202E]
    | set(range(0x2060, 0x2064))  # [0x2060, 0x2063]
)


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
    if (
        o == 0x0000
        or 0x200B <= o <= 0x200F
        or 0x2028 <= o <= 0x202E
        or 0x2060 <= o <= 0x2063
    ):
        return 0

    category = unicodedata.category(c)

    # Control characters.
    if category == "Cc":
        return -1

    # Combining characters with zero width.
    if category in ("Me", "Mn"):
        return 0

    # Full/Wide east asian characters.
    if unicodedata.east_asian_width(c) in ("F", "W"):
        return 2

    return 1


def wcswidth(s: str) -> int:
    """Determine how many columns are needed to display a string in a terminal.

    Returns -1 if the string contains non-printable characters.
    """
    width = 0
    it = map(wcwidth, _ucd_normalize("NFC", s))
    for wc in it:
        if wc < 0:
            return -1
        width += wc
    return width
