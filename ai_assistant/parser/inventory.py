"""DS3 inventory grid parser.

Inventory grid starts at offset `0x01A3D0`, with 16-byte records:

    +0  handle (4 bytes, prefix varies by item type — sequence-of-acquisition)
    +4  item ID (4 bytes, u32 LE — high byte = item type)
    +8  count  (4 bytes, u32 LE — stack size; 1 for unique items)
    +12 instance ID / timestamp (4 bytes)

The item type is the high byte of the ID:

    0x00         weapon
    0x10–0x1F    armor (sub-categories use different high bytes)
    0x20         ring
    0x40         good (consumables, key items, spells)

Anything else marks the end of the grid for this slot.

Item ID → name maps are loaded from `data/_weapons.json`, `_armor.json`,
`_ring.json`, `_goods_magic.json` — fetched from alfizari's open-source DS3
save editor. Items not in those maps (some spells / boss souls) appear with
`name=None`.
"""
from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

# Offset from the character-name position to the start of the inventory grid.
# Verified across multiple saves with very different equipment loadouts —
# the layout between the name and the grid is fixed-size.
INVENTORY_OFFSET_FROM_NAME = 996  # = 0x3E4
RECORD_SIZE = 16

# DS3 stores "key items" (quest items, keys, ashes, story flags) in a second,
# separate 16-byte grid at this fixed offset from the name anchor. The two
# grids are separated by ~200 zero records, which exceeds the sentinel
# threshold used by the regular-goods scanner and causes them to be skipped.
# Confirmed across saves 01–40 of the QA corpus: always name_offset + 0x7AA8.
KEY_ITEMS_OFFSET_FROM_NAME = 0x7AA8  # = 31400
_ID_OFF = 4
_COUNT_OFF = 8

# Empty-slot markers inside the grid — skipped, not treated as end-of-grid.
_SENTINELS = frozenset({0x00000000, 0xFFFFFFFF})
# The inventory grid has *internal* sentinel gaps (~26 in a row) between
# sub-sections (goods / weapons / armor / rings appear separated). The real
# end of the grid is a much longer sentinel run — observed at 1,249 in our
# test save. A threshold of 64 comfortably distinguishes the two.
_MAX_RUN_BEFORE_STOP = 64

# Mapping from JSON filename → category key.
_ID_FILES = (
    ("weapon", "_weapons.json"),
    ("armor",  "_armor.json"),
    ("ring",   "_ring.json"),
    ("good",   "_goods_magic.json"),
)


@dataclass
class InventoryItem:
    category: str           # "weapon" | "armor" | "ring" | "good"
    item_id: int
    count: int
    name: Optional[str]     # None if not in the ID map


def _classify(item_id: int) -> Optional[str]:
    """Map an item ID's high byte to a category. Sentinels return None."""
    if item_id in _SENTINELS:
        return None
    high = (item_id >> 24) & 0xFF
    if high == 0x00:
        return "weapon"
    if 0x10 <= high <= 0x1F:
        return "armor"
    if high == 0x20:
        return "ring"
    if high == 0x40:
        return "good"
    return None


def load_id_maps(data_dir: Path) -> Dict[str, Dict[int, str]]:
    """Load DS3 item-ID-to-name maps from the alfizari JSONs in `data_dir`."""
    maps: Dict[str, Dict[int, str]] = {}
    for category, fname in _ID_FILES:
        path = data_dir / fname
        d = json.loads(path.read_text())
        m: Dict[int, str] = {}
        for name, hex_str in d.items():
            raw = bytes(int(b, 16) for b in hex_str.split())
            item_id = struct.unpack("<I", raw)[0]
            m[item_id] = name
        maps[category] = m
    return maps


def _scan_grid(
    payload: bytes,
    start: int,
    id_maps: Optional[Dict[str, Dict[int, str]]],
    max_sentinel_run: int = _MAX_RUN_BEFORE_STOP,
) -> List[InventoryItem]:
    """Scan one 16-byte inventory grid starting at `start` in `payload`."""
    items: List[InventoryItem] = []
    off = start
    end_of_payload = len(payload) - RECORD_SIZE
    run_since_last_item = 0
    while off <= end_of_payload and run_since_last_item < max_sentinel_run:
        item_id = struct.unpack_from("<I", payload, off + _ID_OFF)[0]
        category = _classify(item_id)
        if category is None:
            run_since_last_item += 1
            off += RECORD_SIZE
            continue
        count = struct.unpack_from("<I", payload, off + _COUNT_OFF)[0]
        name = (id_maps or {}).get(category, {}).get(item_id)
        items.append(InventoryItem(category, item_id, count, name))
        run_since_last_item = 0
        off += RECORD_SIZE
    return items


def parse_inventory(
    payload: bytes,
    name_offset: int,
    id_maps: Optional[Dict[str, Dict[int, str]]] = None,
) -> List[InventoryItem]:
    """Walk both inventory grids and return every populated item record.

    DS3 uses two separate 16-byte grids:
      1. Regular goods (consumables, rings, spells) at name_offset + 0x3E4.
      2. Key items (keys, ashes, quest items, story flags) at name_offset + 0x7AA8.
    The two grids are separated by ~200 zero records; this function reads both.
    """
    regular = _scan_grid(payload, name_offset + INVENTORY_OFFSET_FROM_NAME, id_maps)
    key_items = _scan_grid(payload, name_offset + KEY_ITEMS_OFFSET_FROM_NAME, id_maps)
    return regular + key_items
