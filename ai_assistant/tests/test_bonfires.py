"""Regression test for last-bonfire parsing.

The 4-slot save at `save_files/DS30000.sl2` has four characters at four
distinct, user-validated locations. Locks the parser to that ground truth.

User-validated mappings (session 2026-05-28):

    Clodoaldo       → Cemetery of Ash          (ID 4000)
    Frederico       → Firelink Shrine          (ID 4005)
    Melissa         → Kiln of the First Flame  (ID 4100)
    Dark Tarnished  → The Ringed City          (ID 5100)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from parser import inventory, slots

SL2_PATH = Path(__file__).resolve().parents[2] / "save_files" / "DS30000.sl2"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


EXPECTED = {
    "Dark Tarnished": (5100, "The Ringed City"),
    "Frederico":      (4005, "Firelink Shrine"),
    "Melissa":        (4100, "Kiln of the First Flame"),
    "Clodoaldo":      (4000, "Cemetery of Ash"),
}


@pytest.fixture(scope="module")
def loaded_slots():
    if not SL2_PATH.exists():
        pytest.skip(f"save not present: {SL2_PATH}")
    id_maps = inventory.load_id_maps(DATA_DIR)
    return slots.load_slots(SL2_PATH, id_maps=id_maps)


@pytest.mark.parametrize("name,expected", list(EXPECTED.items()), ids=list(EXPECTED.keys()))
def test_last_bonfire_per_character(loaded_slots, name, expected):
    matching = [s for s in loaded_slots if s.name == name]
    assert len(matching) == 1, f"expected one slot named {name!r}, got {len(matching)}"
    slot = matching[0]
    want_id, want_name = expected
    assert slot.last_bonfire_id == want_id, (name, slot.last_bonfire_id)
    assert slot.last_bonfire_name == want_name, (name, slot.last_bonfire_name)
