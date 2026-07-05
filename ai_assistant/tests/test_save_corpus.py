"""Multi-save regression tests.

Each save in `save_files/<folder>/DS30000.sl2` came with an `info.txt`
and/or screenshots that pin down concrete expected values. This file locks
those in as test cases so a future parser change can't quietly regress on
any save we've previously validated.

Each entry below cites the source (info.txt line or screenshot caption) for
its expected value.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from parser import inventory, slots

SAVES_ROOT = Path(__file__).resolve().parents[2] / "save_files"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# Expected values per save, sourced from info.txt + status-screen screenshots.
CASES = [
    # max_level_and_new_game_plus_5/info.txt:
    #   "Max level / All weapons & armor / All magic spells / 603282322 souls"
    # status screenshot: level 802, all attrs 99, name "1205"
    {
        "folder": "max_level_and_new_game_plus_5",
        "slot": 0,
        "name": "1205",
        "level": 802,
        "souls": 603_282_322,
        "attrs": (99, 99, 99, 99, 99, 99, 99, 99, 99),  # VIG ATT END VIT STR DEX INT FTH LCK
        "class": "Mercenary",
        "sex": "Female",
        # info.txt promises lots of items — assert generous floors.
        "min_weapons": 100,
        "min_armor":   150,
        "min_rings":   150,
        "min_goods":   150,
    },
    # sl_715/info.txt: SL 715, 26M souls, attributes listed (LCK=12 is the
    # distinctive value), 99 Ember, +3 rings.
    {
        "folder": "sl_715",
        "slot": 0,
        "name": "Morguls",
        "level": 715,
        # info.txt: "26 Million Souls on the Character" — exact value from
        # status screenshot.
        "souls": 25_943_322,
        "attrs": (99, 99, 99, 99, 99, 99, 99, 99, 12),
        "class": "Knight",
        "sex": "Male",
        "min_weapons": 20,
        "min_armor":   25,
        "min_rings":   40,
        "min_goods":   50,
        # info.txt: "99x Ember"
        "expected_items": {"Ember": 99},
    },
    # usurpation_of_fire_ending/info.txt: only narrative info, no specific
    # numbers. Assert what the parser produces is internally consistent (the
    # values came from a known save state, so they're our reference now).
    {
        "folder": "the_usurpation_of_fire_ending",
        "slot": 0,
        "name": "Male Hero 1",
        "level": 204,
        "souls": 100_000,
        # Attributes not specified in info.txt; values are what the save
        # actually contains and act as a regression anchor.
        "attrs": (57, 25, 46, 40, 21, 50, 0, 55, 0),  # VIG ATT END VIT STR DEX INT FTH LCK
        "class": "Deprived",
        "sex": "Male",
        "min_weapons": 100,
        "min_armor":   200,
        "min_rings":   50,
        "min_goods":   100,
    },
]


@pytest.fixture(scope="module")
def id_maps():
    return inventory.load_id_maps(DATA_DIR)


@pytest.fixture(scope="module")
def loaded_by_case(id_maps):
    """Pre-load all save corpora once, keyed by folder name."""
    out = {}
    for case in CASES:
        sl2 = SAVES_ROOT / case["folder"] / "DS30000.sl2"
        if not sl2.exists():
            continue
        out[case["folder"]] = slots.load_slots(sl2, id_maps=id_maps)
    return out


@pytest.mark.parametrize("case", CASES, ids=[c["folder"] for c in CASES])
def test_slot_summary_matches_expectations(case, loaded_by_case):
    if case["folder"] not in loaded_by_case:
        pytest.skip(f"save not present: {case['folder']}")
    slot = loaded_by_case[case["folder"]][case["slot"]]
    assert slot.name == case["name"], (case["folder"], slot.name)
    assert slot.character_class == case["class"], (case["folder"], slot.character_class)
    assert slot.sex == case["sex"], (case["folder"], slot.sex)
    assert slot.stats is not None
    assert slot.stats.level == case["level"], (case["folder"], slot.stats.level)
    assert slot.stats.souls == case["souls"], (case["folder"], slot.stats.souls)
    actual_attrs = (
        slot.stats.vigor, slot.stats.attunement, slot.stats.endurance,
        slot.stats.vitality, slot.stats.strength, slot.stats.dexterity,
        slot.stats.intelligence, slot.stats.faith, slot.stats.luck,
    )
    assert actual_attrs == case["attrs"], (case["folder"], actual_attrs)


@pytest.mark.parametrize("case", CASES, ids=[c["folder"] for c in CASES])
def test_inventory_meets_floors(case, loaded_by_case):
    if case["folder"] not in loaded_by_case:
        pytest.skip(f"save not present: {case['folder']}")
    slot = loaded_by_case[case["folder"]][case["slot"]]
    from collections import Counter
    cats = Counter(i.category for i in slot.inventory)
    assert cats["weapon"] >= case["min_weapons"], (case["folder"], cats)
    assert cats["armor"]  >= case["min_armor"],   (case["folder"], cats)
    assert cats["ring"]   >= case["min_rings"],   (case["folder"], cats)
    assert cats["good"]   >= case["min_goods"],   (case["folder"], cats)


@pytest.mark.parametrize("case", CASES, ids=[c["folder"] for c in CASES])
def test_inventory_specific_items(case, loaded_by_case):
    if "expected_items" not in case:
        pytest.skip("no specific items to check")
    if case["folder"] not in loaded_by_case:
        pytest.skip(f"save not present: {case['folder']}")
    slot = loaded_by_case[case["folder"]][case["slot"]]
    by_name = {i.name: i.count for i in slot.inventory if i.name}
    for name, want_count in case["expected_items"].items():
        assert name in by_name, f"{name!r} not in inventory for {case['folder']}"
        assert by_name[name] == want_count, (case["folder"], name, by_name[name])
