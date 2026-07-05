"""CLI: `python -m parser.cli <path-to-sl2>` — list all character slots."""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from . import inventory as inv_mod, slots

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python -m parser.cli <path-to-DS30000.sl2>", file=sys.stderr)
        return 2
    sl2 = Path(sys.argv[1])
    if not sl2.exists():
        print(f"file not found: {sl2}", file=sys.stderr)
        return 1

    id_maps = inv_mod.load_id_maps(DATA_DIR)
    summaries = slots.load_slots(sl2, id_maps=id_maps)
    header = (
        f"{'slot':<4} {'name':<10} {'class':<10} {'sex':<6} "
        f"{'lvl':>3} {'playtime':>8}  {'souls':>10}  "
        f"{'wpn':>3} {'arm':>3} {'rng':>3} {'gd':>3}  {'location':<25}"
    )
    print(header)
    print("-" * len(header))
    for s in summaries:
        if s.name is None or s.stats is None:
            print(f"{s.index:<4} (empty)")
            continue
        st = s.stats
        cats = Counter(i.category for i in s.inventory)
        if s.playtime_seconds is not None:
            h, rem = divmod(s.playtime_seconds, 3600)
            m, sec = divmod(rem, 60)
            playtime_str = f"{h:02}:{m:02}:{sec:02}"
        else:
            playtime_str = "-"
        if s.last_bonfire_name:
            loc = s.last_bonfire_name
        elif s.last_bonfire_id is not None:
            loc = f"#{s.last_bonfire_id}"
        else:
            loc = "?"
        print(
            f"{s.index:<4} {s.name:<10} {s.character_class or '?':<10} "
            f"{s.sex or '?':<6} {st.level:>3} {playtime_str:>8}  "
            f"{st.souls:>10,}  "
            f"{cats['weapon']:>3} {cats['armor']:>3} {cats['ring']:>3} {cats['good']:>3}  {loc:<25}"
        )

    # For the first non-empty slot, dump a sample of named items per category.
    first_loaded = next((s for s in summaries if s.inventory), None)
    if first_loaded is not None:
        print(f"\nSample of slot {first_loaded.index} ({first_loaded.name}) inventory:")
        for cat in ("weapon", "armor", "ring", "good"):
            named = [i for i in first_loaded.inventory if i.category == cat and i.name]
            print(f"\n  {cat} ({len(named)} named):")
            for i in named[:5]:
                qty = f" ×{i.count}" if i.count > 1 else ""
                print(f"    {i.name}{qty}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
