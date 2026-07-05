"""Diff two DS3 saves and report semantic event-flag changes.

Usage:
    python scripts/diff_greirat_quest.py <before.sl2> <after.sl2> [--slot N]

The flag section is located via the structural payload walk (see
parser/flags.py), so this works for any character, any slot, regardless of
name_offset / item-registry drift. Output is semantic flag IDs.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from parser import bnd4, crypto
from parser.flags import KNOWN_FLAGS, diff_flags


def load_slot(sl2: Path, slot: int) -> bytes:
    raw = sl2.read_bytes()
    entries = bnd4.parse_entries(raw)
    off, size = entries[slot]
    return crypto.decrypt_entry(raw, off, size)


def label(fid):
    return f"  <- {KNOWN_FLAGS[fid]}" if isinstance(fid, int) and fid in KNOWN_FLAGS else ""


def print_diff(pa: bytes, pb: bytes) -> None:
    sets, clears = diff_flags(pa, pb)
    print(f"Flags newly SET   (0->1): {len(sets)}")
    for fid in sets:
        print(f"  {fid}{label(fid)}")
    print(f"Flags newly CLEARED (1->0): {len(clears)}")
    for fid in clears:
        print(f"  {fid}{label(fid)}")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--slot", type=int, default=0)
    args = ap.parse_args()
    pa = load_slot(Path(args.before), args.slot)
    pb = load_slot(Path(args.after), args.slot)
    print(f"{Path(args.before).name} -> {Path(args.after).name}  (slot {args.slot})\n")
    print_diff(pa, pb)


if __name__ == "__main__":
    main()
