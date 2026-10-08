"""Robust reading and writing of the apps' small JSON settings files.

The files live in %APPDATA%\\Dubrovnik and may be edited by hand, damaged by a
crash or left over from an older version, so nothing here is allowed to raise:
bad data falls back to defaults instead of stopping the app.
"""
import json
import os
import shutil


def read_json(path):
    """Reads a JSON settings file that must contain an object (dict).

    Returns (data, status). status is 'ok', 'missing' or 'corrupt'; data is
    {} unless status is 'ok'. A corrupt file is copied to path + '.bad' so the
    user's edits are not lost when it is replaced by a fresh one.
    """
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data, 'ok'
    except FileNotFoundError:
        return {}, 'missing'
    except (OSError, ValueError):       # unreadable, or not valid JSON
        pass
    try:
        shutil.copyfile(path, path + '.bad')
    except OSError:
        pass
    return {}, 'corrupt'


def write_json(path, data):
    """Writes data as JSON without ever leaving a half-written file: it is
    written to a temporary file first, which then replaces the real one.
    Returns True on success; on failure (e.g. a read-only folder) it reports
    the problem on the console and returns False instead of raising."""
    tmp = path + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, indent=3)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        return True
    except OSError as e:
        print(f'Could not save settings to {path}: {e}')
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False


def clean(cfg, defaults):
    """Returns a dict with every key of defaults: the value from cfg when it
    has a usable type (str, bool or int like the default), else the default."""
    out = {}
    for key, default in defaults.items():
        value = cfg.get(key, default)
        if isinstance(default, bool):
            value = value if isinstance(value, (bool, int)) else default
            value = bool(value)
        elif isinstance(default, int):
            value = int(value) if isinstance(value, (bool, int)) else default
        elif isinstance(default, str):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                value = str(value)          # e.g. 100 typed instead of "100"
            elif not isinstance(value, str):
                value = default
        out[key] = value
    return out


def int_pair(cfg, key_a, key_b, low, high):
    """Returns (cfg[key_a], cfg[key_b]) if both are integers within
    [low, high], else None."""
    a, b = cfg.get(key_a), cfg.get(key_b)
    for v in (a, b):
        if isinstance(v, bool) or not isinstance(v, int) or not low <= v <= high:
            return None
    return a, b
