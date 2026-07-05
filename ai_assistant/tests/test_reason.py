"""Rule-logic tests for reason.py.

These use crafted slot dicts (the same schema extract.py emits) so they run
without any .sl2 corpus on disk. They pin the firing thresholds of the
Option-C rules.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import reason


def _slot(level=30, vig=15, intl=0, fth=0, end=20, inventory=None, bonfire=None):
    stats = {
        "level": level, "souls": 0, "vigor": vig, "attunement": 10,
        "endurance": end, "vitality": 10, "strength": 16, "dexterity": 12,
        "intelligence": intl, "faith": fth, "luck": 7,
    }
    return {
        "index": 4, "name": "T", "class": "Knight", "sex": "Male",
        "level": level, "stats": stats, "equipment": [],
        "inventory": inventory or [], "last_bonfire_name": bonfire,
    }


def _item(name, category="good"):
    return {"category": category, "item_id": 0, "name": name, "count": 1}


# ---- low_vigor --------------------------------------------------------------

def test_low_vigor_fires_when_fragile():
    assert reason.rule_low_vigor(_slot(level=30, vig=15)) is not None


def test_low_vigor_silent_when_adequate():
    assert reason.rule_low_vigor(_slot(level=30, vig=20)) is None


def test_low_vigor_silent_at_low_level():
    assert reason.rule_low_vigor(_slot(level=10, vig=8)) is None


# ---- caster_no_flame --------------------------------------------------------

def test_caster_no_flame_fires_for_hybrid_with_nothing():
    assert reason.rule_caster_no_flame(_slot(intl=15, fth=22)) is not None


def test_caster_no_flame_silent_with_flame():
    slot = _slot(intl=15, fth=22, inventory=[_item("Pyromancy Flame", "weapon")])
    assert reason.rule_caster_no_flame(slot) is None


def test_caster_no_flame_silent_for_pure_stat():
    assert reason.rule_caster_no_flame(_slot(intl=15, fth=5)) is None


# ---- stat_overinvest --------------------------------------------------------

def test_overinvest_fires_for_maxed():
    a = reason.rule_stat_overinvest(_slot(level=802, vig=99, intl=99, fth=99, end=99))
    assert a is not None


def test_overinvest_silent_for_reasonable():
    assert reason.rule_stat_overinvest(_slot(level=80, vig=40, intl=40, fth=40, end=40)) is None


# ---- covenant_badges --------------------------------------------------------

def test_covenant_detected_by_name():
    slot = _slot(inventory=[_item("Way of Blue", "ring")])
    assert reason.rule_covenant_badges(slot) is not None


def test_covenant_silent_when_none():
    assert reason.rule_covenant_badges(_slot()) is None


# ---- location_tips ----------------------------------------------------------

def test_location_tip_for_known_area():
    a = reason.rule_location_tips(_slot(bonfire="Undead Settlement"))
    assert a is not None and "Undead Settlement" in a.title


def test_kiln_is_a_warning():
    a = reason.rule_location_tips(_slot(bonfire="Kiln of the First Flame"))
    assert a is not None and a.severity == "warning"


def test_location_tip_silent_for_unknown_bonfire():
    assert reason.rule_location_tips(_slot(bonfire="Nowhere")) is None


def test_location_tip_silent_when_no_bonfire():
    assert reason.rule_location_tips(_slot(bonfire=None)) is None
