"""Probe slot 9 (Kappa) for metadata fields: playtime, sex, class, deaths,
hollowing. Anchors:

    Kappa playtime  = 12:19:13  = 44,353 s  = 44,353,000 ms
    sex             = Male       (likely 0 in some enum)
    class           = Warrior    (likely 2 in starting-class order;
                                  Knight, Mercenary, Warrior, Herald, Thief,
                                  Assassin, Sorcerer, Pyromancer, Cleric,
                                  Deprived)
    deaths          = 0          (mule save)
    hollowing       = 0          (Yoel quest not started)

Search the slot payload broadly: playtime as several units; class/sex as
u8/u16/u32 in the region around the stat block; print plausible candidates.
"""
from __future__ import annotations

import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parser import slots  # noqa: E402

SAVE = Path(__file__).resolve().parents[2] / "DS30000.sl2"

PLAYTIME_S = 12 * 3600 + 19 * 60 + 13  # 44353

# Stat block we already located.
STATS_OFF = 0x019FA8
NAME_OFF  = 0x019FEC


def find_all(haystack: bytes, needle: bytes) -> list[int]:
    out = []
    start = 0
    while True:
        i = haystack.find(needle, start)
        if i < 0:
            return out
        out.append(i)
        start = i + 1


def main() -> None:
    summaries = slots.load_slots(SAVE)
    pl = summaries[9].payload

    # 1) Playtime in several plausible units.
    print(f"--- playtime search (Kappa={PLAYTIME_S} s) ---")
    for label, needle in [
        ("u32 LE seconds",     struct.pack("<I", PLAYTIME_S)),
        ("u32 LE milliseconds", struct.pack("<I", PLAYTIME_S * 1000)),
        ("u32 LE 1/30 seconds",  struct.pack("<I", PLAYTIME_S * 30)),
        ("u32 LE 1/60 seconds",  struct.pack("<I", PLAYTIME_S * 60)),
        ("u64 LE milliseconds", struct.pack("<Q", PLAYTIME_S * 1000)),
    ]:
        offs = find_all(pl, needle)
        if offs:
            print(f"  {label:<22}  {len(offs)} hits — first 6: " +
                  ", ".join(f"0x{o:06X}" for o in offs[:6]))
        else:
            print(f"  {label:<22}  (no hit)")

    # 2) Dump a 256-byte window around the stat block, looking for low-value
    # u8/u16/u32 fields. Class=Warrior (2?), sex=Male (0?), deaths=0, hollow=0.
    print(f"\n--- u32 LE values in 0x{STATS_OFF - 64:06X}..0x{STATS_OFF:06X} (pre-stats) ---")
    pre = pl[STATS_OFF - 64 : STATS_OFF]
    for i in range(0, len(pre), 4):
        v = struct.unpack_from("<I", pre, i)[0]
        if v < 256:
            print(f"  0x{STATS_OFF - 64 + i:06X}  u32={v}")

    print(f"\n--- u32 LE values in 0x{NAME_OFF + 32:06X}..0x{NAME_OFF + 32 + 256:06X} (post-name) ---")
    post = pl[NAME_OFF + 32 : NAME_OFF + 32 + 256]
    for i in range(0, len(post), 4):
        v = struct.unpack_from("<I", post, i)[0]
        if v < 256:
            print(f"  0x{NAME_OFF + 32 + i:06X}  u32={v}")

    # 3) Hexdump the 64 bytes immediately after the name (32 bytes), where
    # class/sex usually sit in FromSoftware saves.
    print(f"\n--- hex 0x{NAME_OFF:06X}..0x{NAME_OFF + 96:06X} (name + 64 trailing) ---")
    for off in range(NAME_OFF, NAME_OFF + 96, 16):
        row = pl[off : off + 16]
        hex_part = " ".join(f"{b:02x}" for b in row)
        ascii_part = "".join(chr(b) if 0x20 <= b < 0x7f else "." for b in row)
        print(f"  0x{off:06X}  {hex_part}  {ascii_part}")


if __name__ == "__main__":
    main()
