"""Diff the event-flag region between a BEFORE/AFTER controlled save pair.

Aligns both saves on the flag GROUP DIRECTORY (found by content), then reports:
  - new / changed directory entries (group_key -> block_index)
  - bits that turned 0->1 and 1->0 in the block region, as (block_rel_byte,bit)

Usage:
  ./venv/bin/python scripts/controlled_diff.py <slot> <before.sl2> <after.sl2>
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parser import bnd4, crypto, userdata as ud_mod
from parser.slots import _find_name_offset
from scripts.find_flag_anchor import find_directory


def load(sl2: Path, slot: int):
    raw = sl2.read_bytes()
    entries = bnd4.parse_entries(raw)
    ud = ud_mod.parse_userdata(crypto.decrypt_entry(raw, *entries[ud_mod.USERDATA_ENTRY_INDEX]))[slot]
    off, size = entries[slot]
    payload = crypto.decrypt_entry(raw, off, size)
    name_off = _find_name_offset(payload, ud.name or "")
    ds, n = find_directory(payload, name_off)
    return payload, name_off, ds, n


def read_dir(p, ds, n):
    return [struct.unpack_from("<HH", p, ds + 4 * j) for j in range(n)]


def main():
    slot = int(sys.argv[1])
    before, after = Path(sys.argv[2]), Path(sys.argv[3])
    pb, nb, dsb, nbn = load(before, slot)
    pa, na, dsa, nan = load(after, slot)

    print(f"BEFORE name=0x{nb:X} dir=0x{dsb:X} entries={nbn}")
    print(f"AFTER  name=0x{na:X} dir=0x{dsa:X} entries={nan}")

    db = dict(read_dir(pb, dsb, nbn))
    da = dict(read_dir(pa, dsa, nan))
    new_groups = sorted(set(da) - set(db))
    gone_groups = sorted(set(db) - set(da))
    print(f"\nNEW directory group_keys (AFTER only): {new_groups}")
    print(f"REMOVED group_keys (BEFORE only): {gone_groups}")
    moved = [(k, db[k], da[k]) for k in sorted(set(db) & set(da)) if db[k] != da[k]]
    if moved:
        print(f"block_index reshuffles (key: before->after): "
              + ", ".join(f"{k}:{b}->{a}" for k, b, a in moved))

    # Diff block region, aligned on directory start. Blocks begin right after
    # the directory (after 4*n bytes). Compare relative to each save's blocks
    # start so a different directory length doesn't misalign.
    blk_b = dsb + 4 * nbn
    blk_a = dsa + 4 * nan
    span = min(len(pb) - blk_b, len(pa) - blk_a, 0x34000)
    set_bits, clr_bits = [], []
    for i in range(span):
        x = pa[blk_a + i] ^ pb[blk_b + i]
        if not x:
            continue
        for bit in range(8):
            if not (x >> bit) & 1:
                continue
            if (pa[blk_a + i] >> bit) & 1:
                set_bits.append((i, bit))
            else:
                clr_bits.append((i, bit))
    print(f"\nblock region: {len(set_bits)} bits 0->1, {len(clr_bits)} bits 1->0")
    for i, bit in (set_bits if len(set_bits) <= 60 else set_bits[:60]):
        print(f"  SET   block_rel=0x{i:X} bit{bit}")
    if len(clr_bits) <= 30:
        for i, bit in clr_bits:
            print(f"  CLR   block_rel=0x{i:X} bit{bit}")


if __name__ == "__main__":
    main()
