"""Locate the event-flag GROUP DIRECTORY by content.

The flag region is [directory][bit blocks]. The directory is a sorted array of
(group_key u16, block_index u16) pairs where block_index runs 0,1,2,3,... and
group_key strictly increases. We find the directory by scanning for the start
of that val=0,1,2,... sequence.

`name + 0x11660` happens to hit the directory start only for some saves; for
others the directory begins earlier/later. This content scan is robust.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.verify_flag_formula import slot_payload, QA_SLOT, SAVE_DIR

KEYITEMS_REL = 0x7AA8
MIN_DIR_ENTRIES = 12   # require this many sequential val entries to confirm


def find_directory(payload: bytes, name_off: int):
    """Return (dir_start, n_entries) or (None, 0)."""
    lo = name_off + KEYITEMS_REL
    hi = min(name_off + 0x14000, len(payload) - 4 * MIN_DIR_ENTRIES)
    for pos in range(lo, hi, 2):
        # candidate: first pair must be (key>=1, val=0)
        k0, v0 = struct.unpack_from("<HH", payload, pos)
        if v0 != 0 or k0 == 0 or k0 > 0x1000:
            continue
        # verify val=0,1,2,... and key strictly increasing
        ok = True
        prev_k = k0
        count = 1
        for j in range(1, MIN_DIR_ENTRIES):
            k, v = struct.unpack_from("<HH", payload, pos + 4 * j)
            if v != j or k <= prev_k or k > 0x4000:
                ok = False
                break
            prev_k = k
            count = j + 1
        if ok:
            # extend to full length
            j = MIN_DIR_ENTRIES
            while True:
                k, v = struct.unpack_from("<HH", payload, pos + 4 * j)
                if v != j or k <= prev_k:
                    break
                prev_k = k
                j += 1
            return pos, j
    return None, 0


def main():
    for sv in sorted(SAVE_DIR.glob("[0-9][0-9]_*.sl2")):
        payload, name_off, _ = slot_payload(sv, QA_SLOT)
        ds, n = find_directory(payload, name_off)
        if ds is None:
            print(f"{sv.name[:2]} NOT FOUND")
            continue
        rel = ds - name_off
        last_k = struct.unpack_from("<HH", payload, ds + 4 * (n - 1))[0]
        print(f"{sv.name[:2]} dir=0x{ds:X} (name+0x{rel:X})  entries={n}  "
              f"max_group_key=0x{last_k:X}({last_k})")


if __name__ == "__main__":
    main()
