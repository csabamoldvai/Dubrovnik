"""The Assistant's credentials (Help > Assistant Settings), no GUI code.

They are kept in their own file, %APPDATA%\\Dubrovnik\\assistant.cfg, apart from the
other settings. The API key is stored encrypted for the current Windows user (DPAPI),
so the file is of no use on another account or machine. Environment variables are
still honoured for whatever is left empty here (see assistant.resolve).

    cfg = assistant_config.load(folder)       # {'provider': 'anthropic', 'apiKey': ...}
    assistant_config.save(folder, cfg)
"""
import base64
import os

from dubLibs import cfgfile

FILE_NAME = 'assistant.cfg'
KEYS = ('provider', 'apiKey', 'baseUrl', 'model', 'vertexProject', 'vertexRegion')
SECRET = 'apiKey'
PROVIDERS = ('anthropic', 'gateway', 'bedrock', 'vertex')


def _dpapi(data, protect):
    """Windows Data Protection API: encrypts or decrypts bytes for this user"""
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]

    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    buf = ctypes.create_string_buffer(data, len(data))
    source = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    result = Blob()
    function = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    if not function(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(result)):
        raise OSError('Windows could not protect the data')
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(result.pbData, ctypes.c_void_p))


def protect(text):
    """The text as it is written to the file: 'dpapi:<base64>' (or 'plain:<base64>' where
    the Windows API is not there)"""
    if not text:
        return ''
    raw = text.encode('utf-8')
    try:
        return 'dpapi:' + base64.b64encode(_dpapi(raw, True)).decode('ascii')
    except (OSError, AttributeError):
        return 'plain:' + base64.b64encode(raw).decode('ascii')


def unprotect(stored):
    """The text of a protect() result; '' if it cannot be read (another user's file)"""
    try:
        kind, _, body = stored.partition(':')
        raw = base64.b64decode(body.encode('ascii'), validate=True)
        if kind == 'dpapi':
            raw = _dpapi(raw, False)
        elif kind != 'plain':
            return ''
        return raw.decode('utf-8')
    except (OSError, AttributeError, ValueError):
        return ''


def load(folder):
    """The saved credentials as a dict with every key of KEYS (empty strings if none)"""
    data, _ = cfgfile.read_json(os.path.join(folder, FILE_NAME))
    cfg = {k: v if isinstance(v, str) else '' for k, v in
           ((k, data.get(k, '')) for k in KEYS)}
    cfg[SECRET] = unprotect(cfg[SECRET])
    if cfg['provider'] not in PROVIDERS:
        cfg['provider'] = ''
    return cfg


def save(folder, cfg):
    """Writes the credentials; returns True on success"""
    data = {k: str(cfg.get(k, '')).strip() for k in KEYS}
    data[SECRET] = protect(data[SECRET])
    return cfgfile.write_json(os.path.join(folder, FILE_NAME), data)
