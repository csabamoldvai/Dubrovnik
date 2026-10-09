"""Help > Documents is built from the files in the 'docs' folder.

Any file type works (PDF, PNG, PPTX, ...): choosing an entry opens the file in
the program Windows uses for that type. The menu text is the file name without
its extension, with underscores shown as spaces. A leading number sets the order
and is not shown:

    01_Board_Schematic_1V2A.pdf   ->  "Board Schematic 1V2A"   (first)
    Board_Photo.png               ->  "Board Photo"

The menu is rebuilt every time it is opened, so a new file appears at once.
"""
import os
import re

IGNORED = {'desktop.ini', 'thumbs.db', '.ds_store'}


def find_documents(folder):
    """Returns [(menu text, full path), ...] for the files in folder, sorted by
    file name. Hidden files and Office lock files (~$...) are skipped."""
    found = []
    try:
        names = sorted(os.listdir(folder), key=str.lower)
    except OSError:
        return found
    for name in names:
        path = os.path.join(folder, name)
        if (not os.path.isfile(path) or name.startswith(('.', '~$'))
                or name.lower() in IGNORED):
            continue
        stem = os.path.splitext(name)[0]
        label = re.sub(r'^\d+[_ -]+', '', stem).replace('_', ' ').strip()
        found.append((label or stem, path))
    return found
