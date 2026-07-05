"""Parse EMEVD decompiled events file to extract:
1. Boss defeat flag IDs (SetEventFlag after HandleBossDefeat)
2. NPC quest state machine flag IDs (BatchSetNetworkconnectedEventFlags ranges)
3. All named SetEventFlag calls in key events

Run from ai_assistant/:
    python scripts/parse_emevd_flags.py
"""
import re
import json
from pathlib import Path

EVENS_FILE = Path(r"C:\Users\user\Desktop\evens.txt")
OUT_FILE = Path(__file__).parent.parent / "data" / "_emevd_flags.json"

text = EVENS_FILE.read_text(encoding="utf-8", errors="ignore")

SET_FLAG  = re.compile(r'SetEventFlag\((\d+),\s*(ON|OFF)\)')
NET_FLAG  = re.compile(r'SetNetworkconnectedEventFlag\((\d+),\s*(ON|OFF)\)')
BATCH_SET = re.compile(r'BatchSetNetworkconnectedEventFlags\((\d+),\s*(\d+),')
EVENT_HDR = re.compile(r'\$Event\((\d+),')
MAP_HDR   = re.compile(r'=== (m\d+_\d+(?:_\d+_\d+)?|common\w*)')


def get_event_text(evt_id: str) -> tuple[str, str]:
    """Return (map_name, event_text) for a given event ID string."""
    m = re.search(r'\$Event\(' + re.escape(evt_id) + r',', text)
    if not m:
        return "?", ""
    end = text.find("$Event(", m.start() + 1)
    evt_text = text[m.start(): end if end != -1 else m.start() + 5000]
    # find map
    map_match = list(MAP_HDR.finditer(text[:m.start()]))
    map_name = map_match[-1].group(1) if map_match else "?"
    return map_name, evt_text


# ------------------------------------------------------------------ #
# 1. Boss defeat flags — SetEventFlag(X, ON) within ~500 chars of
#    HandleBossDefeat(...)
# ------------------------------------------------------------------ #
print("=== Boss defeat flag IDs ===\n")
boss_flags = {}
for m in re.finditer(r'HandleBossDefeat\([^)]+\)', text):
    after = text[m.end(): m.end() + 500]
    before = text[max(0, m.start() - 1000): m.start()]

    # Which event?
    evt_matches = list(EVENT_HDR.finditer(before))
    evt_id = evt_matches[-1].group(1) if evt_matches else "?"

    # Which map?
    map_matches = list(MAP_HDR.finditer(text[: m.start()]))
    map_name = map_matches[-1].group(1) if map_matches else "?"

    flags_on = [int(f) for f, s in SET_FLAG.findall(after) if s == "ON"]
    if flags_on:
        print(f"  Event {evt_id} ({map_name}):  SetEventFlag ON = {flags_on}")
        for fid in flags_on:
            boss_flags[fid] = f"Boss defeat flag set in event {evt_id} ({map_name})"

print()

# ------------------------------------------------------------------ #
# 2. Detailed boss event analysis
# ------------------------------------------------------------------ #
print("=== Specific boss events (all SetEventFlag ON) ===\n")

# These event IDs contain the actual boss defeat logic
boss_event_ids = {
    # m40 = Firelink/Cemetery of Ash
    "14005800": "Iudex Gundyr post-defeat (fires 9319, 6319)",
    "14005830": "Champion Gundyr post-defeat",
    # m30 = High Wall of Lothric
    "13005811": "Vordt of the Boreal Valley defeat",
    "13005831": "Dancer of the Boreal Valley defeat",
    "13005895": "Oceiros / Consumed King area boss defeat",
    # m31 = Undead Settlement
    "13105812": "Curse-Rotted Greatwood defeat",
}

confirmed_boss_flags = {}
for eid, label in boss_event_ids.items():
    map_name, evt_text = get_event_text(eid)
    if not evt_text:
        print(f"  {eid}: NOT FOUND")
        continue
    flags_on = [int(f) for f, s in SET_FLAG.findall(evt_text) if s == "ON"]
    print(f"  Event {eid} ({map_name}) — {label}")
    print(f"    SetEventFlag ON: {flags_on}")
    for fid in flags_on:
        if 0 < fid < 200000:  # skip huge flag IDs that are system flags
            confirmed_boss_flags[fid] = label
    print()

# ------------------------------------------------------------------ #
# 3. NPC quest state machine flag ranges
# ------------------------------------------------------------------ #
print("=== NPC quest state machine flag ranges ===\n")

npc_events = {
    # m40 = Firelink hub NPCs
    "14005520": "Yoel of Londor (Firelink)",
    "14005540": "Anri of Astora (Firelink)",
    "14005560": "Cornyx of the Great Swamp (Firelink)",
    "14005570": "Siegward of Catarina (Firelink / Well)",
    "14005580": "Eygon of Carim (Firelink)",
    "14005586": "Eygon (secondary)",
    "14005600": "Fire Keeper",
    "14005620": "Leonhard (Firelink)",
    "14005640": "Hawkwood (Firelink)",
    "14005660": "Andre (blacksmith)",
    "14005680": "Orbeck of Vinheim (Firelink)",
    "14005700": "Sirris of the Sunless Realms (Firelink)",
    "14005720": "Anri route 2 (Firelink)",
    "14005740": "Yuria of Londor (Firelink)",
    "14005750": "Hawkwood quest (Firelink)",
    "14005760": "Karla (Firelink)",
    "14005780": "Patches (Firelink)",
    # m30 = High Wall of Lothric
    "13005600": "Greirat of the Undead Settlement (High Wall jail)",
    "13005620": "Anri (High Wall)",
    "13005640": "Greirat at Firelink (m30 secondary)",
    # m31 = Undead Settlement
    "13105600": "Yoel of Londor (Undead Settlement entrance)",
    "13105620": "Anri (Undead Settlement)",
    "13105640": "Eygon (Cathedral/Undead Settlement)",
    "13105660": "Irina of Carim (Undead Settlement / sewers)",
    "13105680": "Siegward (windmill/Undead Settlement)",
    "13105700": "Greirat scavenging (m31)",
    "13105720": "Patches (Undead Settlement / Farron)",
}

npc_flag_ranges = {}
for eid, label in npc_events.items():
    map_name, evt_text = get_event_text(eid)
    if not evt_text:
        continue
    batches = BATCH_SET.findall(evt_text)
    net_flags = [int(f) for f, s in NET_FLAG.findall(evt_text) if s == "ON"]
    set_flags = [int(f) for f, s in SET_FLAG.findall(evt_text) if s == "ON"]

    if batches or net_flags or set_flags:
        lo, hi = None, None
        if batches:
            all_lo = [int(b[0]) for b in batches]
            all_hi = [int(b[1]) for b in batches]
            lo, hi = min(all_lo), max(all_hi)

        print(f"  {label} (event {eid}, {map_name}):")
        if lo is not None:
            print(f"    State range: {lo} - {hi}")
        if net_flags:
            print(f"    Quest step flags (SetNetworkconnectedEventFlag ON): {net_flags[:10]}")
        if set_flags:
            print(f"    SetEventFlag ON: {set_flags[:10]}")

        npc_flag_ranges[eid] = {
            "label": label,
            "map": map_name,
            "state_lo": lo,
            "state_hi": hi,
            "quest_flags": net_flags[:10],
        }
        print()

# ------------------------------------------------------------------ #
# 4. Key progress flags — small IDs set in key story moments
# ------------------------------------------------------------------ #
print("=== Key story/bonfire flags (small IDs in map events) ===\n")

# Look at ALL SetEventFlag(X, ON) where X < 10000 across all maps
small_flags = {}  # flag_id -> list of (map, event_id)
for map_match in MAP_HDR.finditer(text):
    map_name = map_match.group(1)
    map_start = map_match.start()
    next_map = MAP_HDR.search(text, map_start + 1)
    map_text = text[map_start: next_map.start() if next_map else len(text)]

    for evt_match in EVENT_HDR.finditer(map_text):
        evt_id = int(evt_match.group(1))
        evt_start = evt_match.start()
        next_evt = map_text.find("$Event(", evt_start + 1)
        evt_text = map_text[evt_start: next_evt if next_evt != -1 else len(map_text)]

        for flag_match in SET_FLAG.finditer(evt_text):
            fid = int(flag_match.group(1))
            state = flag_match.group(2)
            if state == "ON" and fid < 10000 and fid > 0:
                if fid not in small_flags:
                    small_flags[fid] = []
                small_flags[fid].append((map_name, evt_id))

print(f"Found {len(small_flags)} unique small flag IDs (1-9999) with SetEventFlag ON")
print()
print("Flag IDs with single occurrence (most likely to be meaningful):")
for fid in sorted(small_flags):
    occurrences = small_flags[fid]
    maps = set(m for m, e in occurrences)
    print(f"  flag {fid:>6}:  {occurrences[:5]}")

# ------------------------------------------------------------------ #
# 5. Write output JSON
# ------------------------------------------------------------------ #
output = {
    "boss_defeat_flags": boss_flags,
    "confirmed_boss_flags": confirmed_boss_flags,
    "npc_quest_event_ranges": npc_flag_ranges,
    "small_progress_flags": {str(k): v for k, v in small_flags.items()},
}
OUT_FILE.write_text(json.dumps(output, indent=2))
print(f"\nWrote {OUT_FILE}")
