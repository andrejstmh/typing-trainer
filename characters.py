import unicodedata


def normalize_characters(chars):
    """Deduplicate NFC characters; curses history uses one cell per character."""
    chars = unicodedata.normalize("NFC", chars)
    if not chars or any(
        not ch.isprintable()
        or unicodedata.category(ch).startswith(("C", "M"))
        or unicodedata.east_asian_width(ch) in ("W", "F")
        for ch in chars
    ):
        raise ValueError("Invalid character set")
    return "".join(dict.fromkeys(chars))
