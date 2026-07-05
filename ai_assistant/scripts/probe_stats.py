"""One-off exploration: locate the stat block in a decrypted DS3 slot.

Anchored on slot 9 (Kappa) whose values are known from the in-game status
screen:

    souls           = 6,473,870
    required souls  = 775
    level           = 7
    sex             = Male
    class           = Warrior
    playtime        = 12:19:13 (44,353 s)

    VIG=14 ATT=6 END=12 VIT=11 STR=16 DEX=9 INT=8 FTH=9 LCK=11

Once offsets are confirmed, they get baked into `parser/stats.py`.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parser import slots  # noqa: E402

SAVE = Path(sys.argv[1]) if len(sys.argv) > 1 else (
    Path(__file__).resolve().parents[2] / "DS30000.sl2"
)

KAPPA_INDEX = 9
KAPPA_SOULS = 6_473_870
KAPPA_REQUIRED = 775
KAPPA_LEVEL = 7
KAPPA_PLAYTIME_S = 12 * 3600 + 19 * 60 + 13  # 44353
# (VIG, ATT, END, VIT, STR, DEX, INT, FTH, LCK)
KAPPA_ATTRS = (14, 6, 12, 11, 16, 9, 8, 9, 11)
ATTR_NAMES = ("VIG", "ATT", "END", "VIT", "STR", "DEX", "INT", "FTH", "LCK")


def find_all(haystack: bytes, needle: bytes) -> list[int]:
    offs = []
    start = 0
    while True:
        i = haystack.find(needle, start)
        if i < 0:
            return offs
        offs.append(i)
        start = i + 1


def hexdump(buf: bytes, base: int, width: int = 16) -> None:
    for i in range(0, len(buf), width):
        row = buf[i : i + width]
        hex_part = " ".join(f"{b:02x}" for b in row)
        ascii_part = "".join(chr(b) if 0x20 <= b < 0x7f else "." for b in row)
        print(f"  0x{base + i:06X}  {hex_part:<48}  {ascii_part}")


def main() -> None:
    summaries = slots.load_slots(SAVE)
    kappa = summaries[KAPPA_INDEX]
    pl = kappa.payload
    name_off = 0x19FEC

    print(f"Kappa payload length: {len(pl):,}")

    # Souls offset confirms the stat block is right before the name.
    souls_off = find_all(pl, struct.pack("<I", KAPPA_SOULS))[0]
    print(f"souls (u32 LE) at 0x{souls_off:06X}  (name at 0x{name_off:06X})")

    # Dump a fat window around the souls offset.
    start = max(0, souls_off - 96)
    end = min(len(pl), name_off + 128)
    print(f"\n--- bytes from 0x{start:06X} to 0x{end:06X} ---")
    hexdump(pl[start:end], start)

    # Try locating each attribute individually as u32 LE in the same window,
    # to see if they're scattered, in a different type, or have padding.
    print("\n--- per-attribute search as u32 LE within window ---")
    win = pl[start:end]
    for name, val in zip(ATTR_NAMES, KAPPA_ATTRS):
        offs = find_all(win, struct.pack("<I", val))
        rel = ", ".join(f"+0x{o:04X}" for o in offs[:6])
        print(f"  {name}={val:3}  offsets: {rel or '(none)'}")

    # And as u8 (single byte), within the same window.
    print("\n--- per-attribute search as u8 within window ---")
    for name, val in zip(ATTR_NAMES, KAPPA_ATTRS):
        offs = find_all(win, bytes([val]))
        rel = ", ".join(f"+0x{o:04X}" for o in offs[:8])
        print(f"  {name}={val:3}  offsets: {rel or '(none)'}")


if __name__ == "__main__":
    main()
