"""Map the equipment-slot region in slot payload (between header and stats).

The earlier probe found item records starting at ~0x60 with handles like
0x90820000, 0x90820001, ... (armor) and 0x80820003, 0x80820005, ... (weapon).
These are NOT 16-byte inventory records — they have a different cadence.

Approach: walk the region byte-by-byte looking for 4-byte aligned u32 values
whose pattern matches an item-handle prefix (0x90820xxx for armor, 0x80820xxx
for weapon), and report the (offset, handle, item_id_at_+4) for each.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parser import inventory, slots  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "data"
SAVE = Path(__file__).resolve().parents[2] / "DS30000.sl2"

# We expect handles like 0x8082NNNN (weapon-slot-style) or 0x9082NNNN
# (armor-slot-style). Mask the low 16 bits and check the high 16 bits.
HANDLE_PREFIXES = (0x80820000, 0x90820000, 0xA0820000, 0xC0820000)


def main() -> None:
    summaries = slots.load_slots(SAVE)
    pl = summaries[9].payload
    id_maps = inventory.load_id_maps(DATA)

    # Build a flat id->name map for any category for quick lookup.
    flat: dict[int, tuple[str, str]] = {}
    for cat, m in id_maps.items():
        for iid, name in m.items():
            flat[iid] = (cat, name)

    print(f"Scanning slot 9 payload for equipment-region item records "
          f"(prefixes 0x8082_/0x9082_ etc.):\n")

    print(f"{'offset':<10} {'handle':<12} {'item_id':<12} {'cat':<7} {'name':<28} {'next u32 (count?)':>18}")
    print("-" * 92)
    for off in range(0, 0x019F00, 4):
        handle = struct.unpack_from("<I", pl, off)[0]
        prefix = handle & 0xFFFF0000
        if prefix not in HANDLE_PREFIXES:
            continue
        item_id = struct.unpack_from("<I", pl, off + 4)[0]
        cat, name = flat.get(item_id, ("?", "?"))
        # Show the next u32 — likely a count or sub-slot index.
        nxt = struct.unpack_from("<I", pl, off + 8)[0]
        # Only print if item_id classifies as an item (so we skip lookup noise).
        from parser.inventory import _classify
        if _classify(item_id) is None:
            continue
        print(f"0x{off:06X}  0x{handle:08X}  0x{item_id:08X}   {cat:<7} {name[:26]:<28}  {nxt:>18}")


if __name__ == "__main__":
    main()
