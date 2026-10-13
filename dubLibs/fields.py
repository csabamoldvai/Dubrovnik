"""Checking the text of an entry box (no GUI code)."""


def parseField(name, text, base=16, signed=False):
    """Validates an entry-box string and returns it as an int.
    Raises ValueError with a user-readable message if it is empty or invalid."""
    text = text.strip()
    if text == '':
        raise ValueError(f'"{name}" is empty. Enter a value.')
    try:
        value = int(text, base)
    except ValueError:
        kind = 'hexadecimal' if base == 16 else 'decimal'
        raise ValueError(f'"{name}" is not a valid {kind} number: {text}')
    if value < 0 and not signed:
        raise ValueError(f'"{name}" must not be negative: {text}')
    return value
