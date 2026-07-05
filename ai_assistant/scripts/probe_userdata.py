"""Probe BND4 entry 10 (user-data) — the load-screen index that stores
per-slot name + level + location + playtime.

Anchors (Kappa, slot 9):
    name       = "Kappa"
    level      = 7
    playtime_s = 44_353  (12:19:13)
    location   = "Firelink Shrine"
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parser import bnd4, crypto  # noqa: E402

SAVE = Path(__file__).resolve().parents[2] / "DS30000.sl2"


def hexdump(buf: bytes, base: int, width: int = 32) -> None:
    for i in range(0, len(buf), width):
        row = buf[i : i + width]
        hex_part = " ".join(f"{b:02x}" for b in row)
        ascii_part = "".join(chr(b) if 0x20 <= b < 0x7f else "." for b in row)
        print(f"  0x{base + i:06X}  {hex_part}  {ascii_part}")


def main() -> None:
    raw = SAVE.read_bytes()
    entries = bnd4.parse_entries(raw)
    pl = crypto.decrypt_entry(raw, *entries[10])
    print(f"entry 10 decrypted length: {len(pl):,} bytes\n")

    # Slot occupancy: souls_givifier says offsets 4244-4254 (10 bytes).
    occ = pl[4244 : 4254]
    print(f"slot occupancy bytes @ 4244-4254: {occ.hex()}")

    # Per-slot records start at 4254. Find every Greek-letter name and its
    # offset.
    expected = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon",
                "Zeta", "Eta", "Theta", "Iota", "Kappa"]
    name_offs = []
    for name in expected:
        needle = name.encode("utf-16-le")
        i = pl.find(needle)
        name_offs.append((name, i))
        print(f"  {name:<8}  @ 0x{i:06X} = {i}")

    # Per-slot record size = consistent stride between names?
    print("\ninter-slot strides:")
    for (a_name, a_off), (b_name, b_off) in zip(name_offs, name_offs[1:]):
        print(f"  {a_name:<8} -> {b_name:<8}  delta = {b_off - a_off}")

    # Now look around Kappa's name for playtime (44353 s = 0xAD41, ms = 0x02A380A8).
    kappa_off = name_offs[-1][1]
    print(f"\n--- search for Kappa playtime values within Kappa record ---")
    record_start = kappa_off - 32  # back up a little
    record_end = kappa_off + 600   # extend forward
    region = pl[record_start : record_end]
    for label, needle in [
        ("u32 LE seconds (44353)", struct.pack("<I", 44353)),
        ("u32 LE ms (44353000)",   struct.pack("<I", 44353000)),
        ("u32 LE 1/30s",            struct.pack("<I", 44353 * 30)),
    ]:
        offs = []
        start = 0
        while True:
            i = region.find(needle, start)
            if i < 0:
                break
            offs.append(record_start + i)
            start = i + 1
        print(f"  {label:<24}  hits: {[hex(o) for o in offs]}")

    # Dump bytes around Kappa's record.
    print(f"\n--- hexdump around Kappa name @ 0x{kappa_off:06X} (start - 32, length 256) ---")
    hexdump(pl[kappa_off - 32 : kappa_off + 256 - 32], kappa_off - 32)


if __name__ == "__main__":
    main()
