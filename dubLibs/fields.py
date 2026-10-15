"""Checking the text of an entry box (no GUI code)."""


def parseField(name, text, base=16, signed=False, digits=None):
    """Validates an entry-box string and returns it as an int.
    digits: the exact number of hex digits required (base 16 only).
    Raises ValueError with a user-readable message if it is empty or invalid."""
    text = text.strip()
    if text == '':
        raise ValueError(f'"{name}" is empty. Enter a value.')
    if digits is not None and not (
            len(text) == digits and all(c in '0123456789abcdefABCDEF' for c in text)):
        raise ValueError(f'"{name}" must be exactly {digits} hex digits: {text}')
    try:
        value = int(text, base)
    except ValueError:
        kind = 'hexadecimal' if base == 16 else 'decimal'
        raise ValueError(f'"{name}" is not a valid {kind} number: {text}')
    if value < 0 and not signed:
        raise ValueError(f'"{name}" must not be negative: {text}')
    return value
