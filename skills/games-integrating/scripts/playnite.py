#!/usr/bin/env python3
import json
import struct
import sys
import uuid
from datetime import datetime, timedelta, timezone

PAGE = 4096
HEADER = 25
DATA, EXTEND = 4, 5


def cstring(b, i):
    j = b.index(0, i)
    return b[i:j].decode("utf-8"), j + 1


def element(b, i, t):
    if t == 0x01:
        return struct.unpack_from("<d", b, i)[0], i + 8
    if t == 0x02:
        n = struct.unpack_from("<i", b, i)[0]
        return b[i + 4:i + 3 + n].decode("utf-8"), i + 4 + n
    if t in (0x03, 0x04):
        n = struct.unpack_from("<i", b, i)[0]
        d = document(b, i)
        return (list(d.values()) if t == 0x04 else d), i + n
    if t == 0x05:
        n, sub = struct.unpack_from("<iB", b, i)
        raw = b[i + 5:i + 5 + n]
        return (str(uuid.UUID(bytes_le=raw)) if sub == 4 else raw.hex()), i + 5 + n
    if t == 0x07:
        return b[i:i + 12].hex(), i + 12
    if t == 0x08:
        return b[i] == 1, i + 1
    if t == 0x09:
        ms = struct.unpack_from("<q", b, i)[0]
        return (datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=ms)).isoformat(), i + 8
    if t == 0x0A:
        return None, i
    if t == 0x10:
        return struct.unpack_from("<i", b, i)[0], i + 4
    if t == 0x12:
        return struct.unpack_from("<q", b, i)[0], i + 8
    if t == 0x13:
        return b[i:i + 16].hex(), i + 16
    if t in (0xFF, 0x7F):
        return None, i
    raise ValueError(f"bson type {t:#x}")


def document(b, i):
    end = i + struct.unpack_from("<i", b, i)[0] - 1
    i += 4
    d = {}
    while i < end:
        t = b[i]
        k, i = cstring(b, i + 1)
        d[k], i = element(b, i, t)
    return d


def documents(path):
    with open(path, "rb") as f:
        raw = f.read()
    pages = [raw[o:o + PAGE] for o in range(0, len(raw), PAGE)]
    for p in pages:
        if p[4] != DATA:
            continue
        count = struct.unpack_from("<H", p, 13)[0]
        i = HEADER
        for _ in range(count):
            _, ext, size = struct.unpack_from("<HIH", p, i)
            data = p[i + 8:i + 8 + size]
            i += 8 + size
            while ext != 0xFFFFFFFF:
                e = pages[ext]
                n = struct.unpack_from("<H", e, 13)[0]
                data += e[HEADER:HEADER + n]
                ext = struct.unpack_from("<I", e, 9)[0]
            yield document(data, 0)


if __name__ == "__main__":
    for doc in documents(sys.argv[1]):
        print(json.dumps(doc, ensure_ascii=False))
