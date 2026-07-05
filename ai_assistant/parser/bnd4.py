"""BND4 container parser — the FromSoftware archive format used by .sl2 saves.

A `.sl2` file is a BND4 archive containing N internal files. For DS3, the first
10 are character slots and the remainder are system files (settings, etc).

Each entry's data block contains a small header followed by an AES-CBC
ciphertext that decrypts to the actual slot payload — see `crypto.py`.
"""
from __future__ import annotations

import struct
from typing import List, Tuple

MAGIC = b"BND4"
NUM_ENTRIES_OFFSET = 0x0C
ENTRY_TABLE_OFFSET = 0x40
ENTRY_SIZE = 0x20
ENTRY_SIZE_FIELD = 0x08
ENTRY_DATA_OFFSET_FIELD = 0x10


def parse_entries(raw: bytes) -> List[Tuple[int, int]]:
    """Return `(data_offset, size)` for every internal file in the archive."""
    if raw[:4] != MAGIC:
        raise ValueError(f"not a BND4 archive (magic={raw[:4]!r})")
    num = struct.unpack_from("<I", raw, NUM_ENTRIES_OFFSET)[0]
    entries: List[Tuple[int, int]] = []
    for i in range(num):
        base = ENTRY_TABLE_OFFSET + i * ENTRY_SIZE
        size = struct.unpack_from("<I", raw, base + ENTRY_SIZE_FIELD)[0]
        data_off = struct.unpack_from("<I", raw, base + ENTRY_DATA_OFFSET_FIELD)[0]
        entries.append((data_off, size))
    return entries
