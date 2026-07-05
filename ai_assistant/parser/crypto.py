"""DS3 save-file decryption.

Each BND4 entry is laid out as:

    [16 bytes hash][16 bytes IV][AES-CBC ciphertext]

The plaintext starts with a `uint32` length prefix followed by the payload.

The AES key is public and identical across all DS3 installations. It is reused
by jtesta/souls_givifier, alfizari's DS3 Save Editor, Yapped Rollo, and other
open-source DS3 tooling. Anti-tamper is provided by the hash field, not by key
secrecy.
"""
from __future__ import annotations

import struct

from Crypto.Cipher import AES

DS3_KEY = bytes([
    0xFD, 0x46, 0x4D, 0x69, 0x5E, 0x69, 0xA3, 0x9A,
    0x10, 0xE3, 0x19, 0xA7, 0xAC, 0xE8, 0xB7, 0xFA,
])

HASH_LEN = 16
IV_LEN = 16
LENGTH_PREFIX = 4


def decrypt_entry(raw: bytes, data_off: int, size: int) -> bytes:
    """Decrypt one BND4 entry to its plaintext payload."""
    blob = raw[data_off : data_off + size]
    iv = blob[HASH_LEN : HASH_LEN + IV_LEN]
    ct = blob[HASH_LEN + IV_LEN :]
    pt = AES.new(DS3_KEY, AES.MODE_CBC, iv).decrypt(ct)
    length = struct.unpack_from("<I", pt, 0)[0]
    return pt[LENGTH_PREFIX : LENGTH_PREFIX + length]
