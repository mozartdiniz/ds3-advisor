"""Quest state evaluator.

Loads a quest JSON from decision_making_files/ and evaluates it against a
parsed slot state (the dict produced by extract.py).

Usage:
    python quest_evaluator.py <save.sl2> <quest_json>
    python quest_evaluator.py save_files/01_created_character.sl2 decision_making_files/irina_of_carim.json

Or import and call from other scripts:
    from quest_evaluator import evaluate_quest, load_quest
    quest = load_quest("decision_making_files/irina_of_carim.json")
    result = evaluate_quest(quest, slot_state)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _inventory_names(slot: dict) -> set[str]:
    """Flatten inventory + equipment into a set of resolved item names."""
    names: set[str] = set()
    for entry in slot.get("inventory", []):
        name = entry.get("name")
        if name:
            names.add(name)
    for entry in slot.get("equipment", []):
        name = entry.get("name")
        if name:
            names.add(name)
    return names


def _flags_set(slot: dict) -> set[int]:
    """Return the set of flag IDs that are set in this slot.

    extract.py stores flags_set as {label_string: bool}. We reverse-map labels
    back to IDs using KNOWN_FLAGS so the evaluator can check by numeric ID.
    """
    from parser.flags import KNOWN_FLAGS  # noqa: PLC0415
    flags_data = slot.get("flags_set", {})
    if not isinstance(flags_data, dict):
        return set()
    label_to_id = {label: fid for fid, label in KNOWN_FLAGS.items()}
    return {
        label_to_id[label]
        for label, val in flags_data.items()
        if val and label in label_to_id
    }


def _check(condition: dict, quest: dict, inventory: set[str], flags: set[int], slot: dict) -> bool:
    """Evaluate a single condition dict against current save state."""
    check = condition["check"]
    groups = quest.get("item_groups", {})
    registry = quest.get("flag_registry", {})

    def resolve_group(group_key: str) -> list[str]:
        entry = groups.get(group_key, {})
        if isinstance(entry, dict):
            return entry.get("items", [])
        if isinstance(entry, list):
            return entry
        return []

    def resolve_flag_id(flag_key: str) -> int | None:
        entry = registry.get(flag_key, {})
        if not entry.get("readable", False):
            return None  # not yet readable — skip the check
        return entry.get("id")

    if check == "has_item":
        return condition["item"] in inventory

    if check == "missing_item":
        return condition["item"] not in inventory

    if check == "has_any_item":
        items = resolve_group(condition["group"]) if "group" in condition else condition.get("items", [])
        return any(i in inventory for i in items)

    if check == "missing_all_items":
        items = resolve_group(condition["group"]) if "group" in condition else condition.get("items", [])
        return all(i not in inventory for i in items)

    if check == "has_all_items":
        items = resolve_group(condition["group"]) if "group" in condition else condition.get("items", [])
        return all(i in inventory for i in items)

    if check == "has_flag":
        flag_id = resolve_flag_id(condition["flag_key"])
        if flag_id is None:
            return False  # unknown flag — conservatively false
        return flag_id in flags

    if check == "missing_flag":
        flag_id = resolve_flag_id(condition["flag_key"])
        if flag_id is None:
            return True   # unknown flag — conservatively treat as absent
        return flag_id not in flags

    if check == "has_any_flag":
        flag_ids = [resolve_flag_id(k) for k in condition.get("flag_keys", [])]
        return any(fid in flags for fid in flag_ids if fid is not None)

    if check == "has_bonfire_area":
        bonfire_name = slot.get("last_bonfire_name") or ""
        return condition["area"].lower() in bonfire_name.lower()

    if check == "missing_bonfire_area":
        bonfire_name = slot.get("last_bonfire_name") or ""
        return condition["area"].lower() not in bonfire_name.lower()


    raise ValueError(f"Unknown condition check type: {check!r}")


def _eval_conditions(conditions: dict, quest: dict, inventory: set[str], flags: set[int], slot: dict) -> bool:
    """Evaluate a conditions block (may have all_of / any_of / none_of / fallback)."""
    if conditions.get("fallback"):
        return True

    results: list[bool] = []

    if "all_of" in conditions:
        results.append(all(_check(c, quest, inventory, flags, slot) for c in conditions["all_of"]))

    if "any_of" in conditions:
        results.append(any(_check(c, quest, inventory, flags, slot) for c in conditions["any_of"]))

    if "none_of" in conditions:
        results.append(not any(_check(c, quest, inventory, flags, slot) for c in conditions["none_of"]))

    if not results:
        return True  # no conditions specified → always matches

    return all(results)


def evaluate_quest(quest: dict, slot: dict) -> dict:
    """
    Evaluate a quest against a single slot state.

    Returns:
        {
          "quest_id": str,
          "active_phase": phase_dict | None,
          "active_warnings": [warning_dict, ...],
        }
    """
    inventory = _inventory_names(slot)
    flags = _flags_set(slot)

    # Find first matching phase
    active_phase = None
    for phase in quest.get("phases", []):
        conditions = phase.get("conditions", {"fallback": True})
        if _eval_conditions(conditions, quest, inventory, flags, slot):
            active_phase = phase
            break

    # Evaluate always-check warnings
    active_warnings = []
    for warning in quest.get("always_check_warnings", []):
        conditions = warning.get("conditions", {"fallback": False})
        if _eval_conditions(conditions, quest, inventory, flags, slot):
            active_warnings.append(warning)

    return {
        "quest_id": quest.get("_meta", {}).get("quest_id", "unknown"),
        "npc": quest.get("_meta", {}).get("npc", ""),
        "active_phase": active_phase,
        "active_warnings": active_warnings,
    }


def load_quest(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def format_result(result: dict) -> str:
    lines: list[str] = []
    lines.append(f"=== {result['npc']} questline ===")

    phase = result.get("active_phase")
    if phase:
        urgency_prefix = ""
        if phase.get("outcome") == "fail":
            urgency_prefix = "❌ FAIL — "
        elif phase.get("terminal") and phase.get("outcome", "").startswith("complete"):
            urgency_prefix = "✓ DONE — "
        lines.append(f"Status: {urgency_prefix}{phase['label']}")
        lines.append(f"  {phase['status_message']}")
        if phase.get("next_steps"):
            lines.append("  Next steps:")
            for step in phase["next_steps"]:
                lines.append(f"    • {step}")
    else:
        lines.append("Status: (no matching phase)")

    for warning in result.get("active_warnings", []):
        urgency = warning.get("urgency", "info").upper()
        lines.append(f"\n[{urgency}] {warning['label']}")
        lines.append(f"  {warning['message']}")

    return "\n".join(lines)


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python quest_evaluator.py <save.sl2> <quest.json> [slot_index]")
        sys.exit(1)

    save_path = sys.argv[1]
    quest_path = sys.argv[2]
    slot_index = int(sys.argv[3]) if len(sys.argv) > 3 else None

    # Import here to avoid circular deps when used as a library
    import extract  # noqa: PLC0415

    state = extract.extract(Path(save_path))
    slots = state.get("slots", [])

    if not slots:
        print("No slots found in save file.")
        sys.exit(1)

    quest = load_quest(quest_path)

    # Evaluate against one slot or all occupied slots
    targets = [slots[slot_index]] if slot_index is not None else [s for s in slots if s.get("occupied")]

    for slot in targets:
        slot_name = slot.get("name", "Unknown")
        slot_level = slot.get("level", "?")
        print(f"\n--- Slot: {slot_name} (SL{slot_level}) ---")
        result = evaluate_quest(quest, slot)
        print(format_result(result))


if __name__ == "__main__":
    main()
