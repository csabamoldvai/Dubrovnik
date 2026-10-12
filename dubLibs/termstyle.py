"""Terminal look settings shared by both editions of the Workbench.

The rules live here so that the two programs accept and repair the same
settings (colours, font, size) and offer the same fonts.
"""
import re
import tkinter.font as tkfont

SIZE_MIN, SIZE_MAX = 8, 32                 # Terminal font size, px
HEX_COLOR = re.compile(r'#[0-9a-fA-F]{6}')
WEIGHT_VARIANT = re.compile(
    r'\s(Thin|ExtraLight|Light|SemiLight|Medium|Retina|SemiBold|Bold|ExtraBold)$')
BITMAP_FONTS = {'8514oem', 'Fixedsys', 'Terminal'}   # not for the font list


def clamp_size(size):
    return min(max(size, SIZE_MIN), SIZE_MAX)


def repair(v, defaults):
    """Puts bad Terminal values of the settings dict v back to the defaults:
    colours must be #rrggbb, the font must not be empty, the size is limited
    to SIZE_MIN..SIZE_MAX."""
    for key in ('terminalBg', 'terminalFg', 'terminalSelect'):
        if not HEX_COLOR.fullmatch(v[key]):
            v[key] = defaults[key]
    if not v['terminalFont'].strip():
        v['terminalFont'] = defaults['terminalFont']
    v['terminalFontSize'] = clamp_size(v['terminalFontSize'])


def monospaced_fonts(root):
    """Installed fixed-width fonts, sorted by name. Weight variants (Light,
    SemiBold, ...) and old bitmap fonts are left out."""
    names = set()
    for family in tkfont.families(root):
        if (family.startswith('@') or family in BITMAP_FONTS
                or WEIGHT_VARIANT.search(family)):
            continue
        try:
            if tkfont.Font(root=root, family=family, size=10).metrics('fixed'):
                names.add(family)
        except Exception:
            pass
    return sorted(names, key=str.lower)
