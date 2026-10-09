"""Shared validation for local PNG assets and normalized crop rectangles."""
import math
from pathlib import Path
import struct


def require(ok, message):
    if not ok:
        raise ValueError(message)


def png_bytes(root, relative):
    require(isinstance(relative, str) and relative.strip(), 'Image path must be nonempty text')
    path = Path(relative)
    require(not path.is_absolute(), 'Image paths must be relative')
    resolved = (root / path).resolve()
    require(resolved.is_relative_to(root.resolve()), 'Image path escapes source directory')
    raw = resolved.read_bytes()
    png_size(raw)
    return raw


def png_size(raw):
    require(len(raw) >= 24 and raw[:8] == b'\x89PNG\r\n\x1a\n' and raw[12:16] == b'IHDR', 'Not a PNG with an IHDR header')
    width, height = struct.unpack('>II', raw[16:24])
    require(width > 0 and height > 0, 'Invalid PNG dimensions')
    return width, height


def bbox(value):
    require(isinstance(value, list) and len(value) == 4, 'bbox must be [left, top, right, bottom]')
    require(all(type(v) in (float, int) and math.isfinite(v) for v in value), 'bbox must contain finite numbers')
    left, top, right, bottom = value
    require(0 <= left < right <= 1 and 0 <= top < bottom <= 1, 'bbox must be ordered and within 0..1')
    return value
