"""Regression test: every slot in the canonical test save resolves to its
expected character name. The save isn't checked in — skip if absent."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from parser import inventory, slots

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SAVE_PATH = Path(__file__).resolve().parents[2] / "DS30000.sl2"

# Slot order from the in-game LOAD GAME screen (see ai_assistant_design.md).
EXPECTED_NAMES = [
    "Alpha", "Beta", "Gamma", "Delta", "Epsilon",
    "Zeta", "Eta", "Theta", "Iota", "Kappa",
]


@pytest.fixture(scope="module")
def loaded_slots():
    if not SAVE_PATH.exists():
        pytest.skip(f"test save not present at {SAVE_PATH}")
    id_maps = inventory.load_id_maps(DATA_DIR)
    return slots.load_slots(SAVE_PATH, id_maps=id_maps)


def test_ten_slots(loaded_slots):
    assert len(loaded_slots) == 10


def test_slot_names_match_load_screen(loaded_slots):
    actual = [s.name for s in loaded_slots]
    assert actual == EXPECTED_NAMES


def test_every_slot_has_payload(loaded_slots):
    assert all(len(s.payload) > 0 for s in loaded_slots)


def test_kappa_stats_match_status_screen(loaded_slots):
    """Slot 9 (Kappa) — exact values from the in-game status screenshot."""
    kappa = loaded_slots[9]
    assert kappa.name == "Kappa"
    s = kappa.stats
    assert s is not None
    assert s.level == 7
    assert s.souls == 6_473_870
    assert (s.vigor, s.attunement, s.endurance, s.vitality,
            s.strength, s.dexterity, s.intelligence, s.faith, s.luck) \
        == (14, 6, 12, 11, 16, 9, 8, 9, 11)


def test_all_populated_slots_have_stats(loaded_slots):
    for s in loaded_slots:
        assert s.stats is not None, f"slot {s.index} ({s.name}) has no stats"


def test_kappa_inventory_has_expected_categories(loaded_slots):
    """All 10 slots in this save are clones — Kappa's inventory matches what
    the probe found when sweeping the grid by item-type prefix."""
    kappa = loaded_slots[9]
    cats = Counter(i.category for i in kappa.inventory)
    # Loose floors — the save description claims "all weapons / armor / rings
    # obtained". Storage box (separate from inventory) holds further items.
    assert cats["weapon"] >= 200, cats
    assert cats["armor"] >= 350, cats
    assert cats["ring"] >= 90, cats
    assert cats["good"] >= 150, cats


def test_inventory_resolves_known_items(loaded_slots):
    """Specific items we know are in the save (from the alfizari ID maps and
    the probed grid contents)."""
    names = {i.name for i in loaded_slots[9].inventory if i.name}
    for expected in (
        "Life Ring",          # base ring, ID 0x20004E20
        "Estus Ring",         # increases Estus heal
        "Deserter Armor",     # appears as the first armor in the grid
        "Storm Ruler",        # picked up at Yhorm — proves end-game items present
        "Fire Arrow",         # ammo (weapon category)
    ):
        assert expected in names, f"{expected!r} not found in resolved inventory"


def test_class_and_sex(loaded_slots):
    """All 10 slots are mules built from the same Warrior/Male template."""
    for s in loaded_slots:
        assert s.character_class == "Warrior", (s.index, s.character_class)
        assert s.class_id == 2, (s.index, s.class_id)
        assert s.sex == "Male", (s.index, s.sex)


def test_playtime_matches_load_screen(loaded_slots):
    """Playtime values pulled from BND4 entry 10 — must match the per-slot
    load-screen timestamps captured from the screenshots."""
    # (slot index, hours, minutes, seconds)
    expected = [
        (0, 12, 17, 37),  # Alpha
        (1, 12, 17, 57),  # Beta
        (2, 12, 18, 29),  # Gamma
        (3, 12, 18, 55),  # Delta
        (4, 12, 19, 16),  # Epsilon
        (5, 12, 19, 35),  # Zeta
        (6, 12, 20,  1),  # Eta
        (7, 12, 18, 41),  # Theta
        (8, 12, 18, 57),  # Iota
        (9, 12, 19, 13),  # Kappa
    ]
    for idx, h, m, sec in expected:
        want = h * 3600 + m * 60 + sec
        got = loaded_slots[idx].playtime_seconds
        assert got == want, (
            f"slot {idx} ({loaded_slots[idx].name}): "
            f"expected {h:02}:{m:02}:{sec:02} ({want}s), got {got}s"
        )
