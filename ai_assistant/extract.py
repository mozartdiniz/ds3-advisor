"""extract.py — read a DS3 .sl2 and write a structured JSON state file.

Usage:
    python extract.py <path-to-DS30000.sl2> [-o state.json]

The state file is intentionally readable and diffable:

    {
      "source":   "<absolute path of the .sl2>",
      "save_mtime": "<ISO8601, file modification time>",
      "slots": [
        {
          "index": 0,
          "occupied": true,
          "name": "...",
          "class": "Knight",
          "sex": "Male",
          "level": 715,
          "playtime_seconds": 308135,
          "souls": 25943322,
          "stats": { "vigor": 99, "attunement": 99, ... },
          "inventory": [
            { "category": "weapon", "item_id": 400100, "name": "Fire Arrow", "count": 8 },
            ...
          ]
        },
        ...
      ]
    }

Empty slots appear with `occupied: false` and the rest of the fields null.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from parser import flags as flags_mod, inventory as inv_mod, slots as slots_mod
from parser.slots import _find_name_offset

DATA_DIR = Path(__file__).resolve().parent / "data"


def _slot_to_dict(s: slots_mod.SlotSummary) -> dict:
    occupied = s.name is not None
    flags_set: dict[str, bool] = {}
    if occupied and s.payload:
        bbs = flags_mod.find_bit_blocks_start(s.payload)
        if bbs is not None:
            raw = flags_mod.read_all_known(s.payload, bbs)
            flags_set = {
                flags_mod.KNOWN_FLAGS[fid]: bool(val)
                for fid, val in raw.items()
                if val == 1
            }
    return {
        "index": s.index,
        "occupied": occupied,
        "name": s.name,
        "class": s.character_class,
        "class_id": s.class_id,
        "sex": s.sex,
        "level": s.stats.level if s.stats else None,
        "playtime_seconds": s.playtime_seconds,
        "souls": s.stats.souls if s.stats else None,
        "last_bonfire_id": s.last_bonfire_id,
        "last_bonfire_name": s.last_bonfire_name,
        "stats": asdict(s.stats) if s.stats else None,
        "flags_set": flags_set,
        "equipment": [
            {
                "slot": e.slot,
                "item_id": e.item_id,
                "base_item_id": e.base_item_id,
                "upgrade_level": e.upgrade_level,
                "name": e.name,
            }
            for e in s.equipment
            if e.item_id is not None
        ],
        "inventory": [
            {
                "category": i.category,
                "item_id": i.item_id,
                "name": i.name,
                "count": i.count,
            }
            for i in s.inventory
        ],
    }


def extract(sl2_path: Path) -> dict:
    id_maps = inv_mod.load_id_maps(DATA_DIR)
    summaries = slots_mod.load_slots(sl2_path, id_maps=id_maps)
    mtime = datetime.fromtimestamp(sl2_path.stat().st_mtime, tz=timezone.utc).isoformat()
    return {
        "source": str(sl2_path.resolve()),
        "save_mtime": mtime,
        "slots": [_slot_to_dict(s) for s in summaries],
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("sl2", type=Path, help="path to DS30000.sl2")
    p.add_argument("-o", "--out", type=Path, default=None,
                   help="output JSON path; default: <sl2_dir>/state.json")
    args = p.parse_args()

    if not args.sl2.exists():
        print(f"file not found: {args.sl2}", file=sys.stderr)
        return 1

    out = args.out or args.sl2.parent / "state.json"
    state = extract(args.sl2)
    out.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    n_occupied = sum(1 for s in state["slots"] if s["occupied"])
    print(f"wrote {out}  ({n_occupied}/10 slots populated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
