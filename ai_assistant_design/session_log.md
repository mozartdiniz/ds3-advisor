# Session Log

Chronological notes from each working session. Most-recent session at the bottom.

---

## Snapshot — 2026-05-27

**Working POC pipeline**, run from `ai_assistant/`:

```
python extract.py <save.sl2>          → writes state.json next to the save
python reason.py  <state.json>        → prints advice grouped by slot
python -m parser.cli <save.sl2>       → tabular summary, no JSON
pytest tests/                         → 9 passing, 13 skipped (corpus saves not on disk)
```

### Key decisions made (session 3)

- **Architecture pivot to POC.** Deferred the full server + watcher + PWA stack. POC is just two Python CLIs that read/write JSON. Server/watcher/PWA stay in the design doc as the v1 target, but iterating on parser + rules content doesn't need them.
- **Dynamic name offset.** Hard-coded `0x019FEC` for the name only worked on the Wanderer mule save (all 10 slots have identically-sized item registries). Real saves have variable-size registries that push the name to anywhere from `0x150E8` to `0x27534`. Fix: use the name from userdata (entry 10) as a needle, search the slot for it, anchor every other offset relative to that position. All offsets now stated as deltas from `name_offset`. Mirrors what `souls_givifier` does.
- **Sex is 1 byte at name+34, not 2.** Earlier `u16 == 0x0101 = 257` for sl_715/Usurpation was actually `u8 sex=1 + u8 age-or-bodytype=1`. Sex: 0=Female, 1=Male.
- **Playtime: u32 LE milliseconds at slot payload offset 8.** Cross-checked against load-screen timestamps for all 10 Wanderer slots.
- **Inventory grid: starts at `name_offset + 996`**, 16-byte records, item_id at +4 (high byte = category), count at +8. Internal sentinel gaps up to ~26 records; real end is a much longer (1,200+) sentinel run.
- **Equipment region (`0x60 – 0x019F00`) is an item registry**, not equipped items. 60-byte records, one per upgradeable owned instance. Currently-equipped items are a *separate* list of handles pointing into this registry — not yet located.

---

## Session 2 — Validation pass against real save (2026-05-28)

### Validation pass against `save_files/DS30000.sl2` (4-slot real player save)

Ran the parser against a real player save with 4 populated slots, then walked each slot with the user and validated against ground truth they hold in their head. Results:

| Slot | Name | Class | Lvl | Location | NG | Origin | Parser correct? |
|---|---|---|---|---|---|---|---|
| 0 | Dark Tarnished | Knight | 195 | The Ringed City | **NG+5** | played | ✅ all fields |
| 1 | Frederico | Knight | 171 | Firelink Shrine | NG 0 | item-modded | ✅ all fields |
| 2 | Melissa | Sorcerer | 159 | Kiln of the First Flame | NG 0 | item-modded | ✅ all fields |
| 3 | Clodoaldo | Knight | 9 | Cemetery of Ash | NG 0 | fresh (3min) | ⚠️ empty inventory — see below |

**Key validation wins:**
- Stat block, level, class, sex, playtime, souls — all correct across the four slots.
- Reasoner correctly flagged FAITH 40 + no chime on Melissa (a real "you forgot something" moment that the player confirmed they'd want surfaced).
- Reasoner correctly listed 16 unspent boss souls on Dark Tarnished and 3 on Frederico — counts cross-checked.

**Major discovery: BND4 entry 11 is the event-flag store (and was never documented).**
- `DS30000.sl2` has **12 BND4 entries**, not 11. Entry 11 is 1 MB encrypted and completely uncharted.
- Entry 11 wraps a **DCX-DEFLATE compressed nested BND4**: expands to **13.4 MB** containing 103 sub-entries (one per map area: first is `01350000` = Lothric).
- **Every wiki flag ID tested is present as a u32 LE inside the decompressed payload.** Boss-dead flags (13000800 Vordt, 14100800 SoC, 15110800 Gael, etc.), boss-victory flags, covenant flags — all there.
- Encoding caveat: each flag ID appears in a constant-context record (prefix `00 00 00 00 23 bf 98 00`, suffix `ff ff ff ff 03 00 00 00 00 00 80 bf`) regardless of whether it's set. So these are **schema entries**, not the actual value store. **(Later sessions confirmed entry 11 is schema-only — values are in the slot payload.)**

**Event-flag dictionary scraped:**
- `scripts/scrape_event_flags.py` — DokuWiki HTML walker → `data/_event_flags.json`. 354 flags. CC BY-SA 4.0.
- Coverage: boss kills (all base + DLC), boss victory, covenant unlocks, NPC quest item drops (Cornyx, Karla, Irina, Eygon, Anri, Yuria, Greirat, Orbeck, Siegward, Sirris, Patches, Hawkwood, Leonhard, Shira, Sister Friede), crow trades, one-time loot drops.

**New parser field: `last_bonfire_id` + `last_bonfire_name`:**
- Lives in userdata (BND4 entry 10), per-slot record at byte offset **+50, u16 LE**.
- Confirmed 4-digit IDs: 4000 → Cemetery of Ash, 4005 → Firelink Shrine, 4100 → Kiln of the First Flame, 5100 → The Ringed City (DLC2).
- Pinned in `tests/test_bonfires.py` (4 cases).

**New parser-correctness finding (slot 3, Clodoaldo):**
- The inventory parser only walked the 16-byte inventory grid. For fresh characters whose only possessions are starting gear (all upgradeable), the parser reported zero items.
- Action: add equipment slot reader to surface currently-equipped items.

---

## Session 3 — 20-save QA corpus + equipment reader (2026-05-28, continued)

### 20-save QA corpus — full validation pass

Created 20 sequential save files in `save_files/` (named `01_created_character_nothing_done.sl2` → `20_Light_the_Undead_Settlement_Bonfire.sl2`). Each captures one key event in a fresh Knight playthrough ("QA", slot 4). All 20 saves parsed without errors. No validation failures.

| Step | Event | Lvl | Key validation |
|---|---|---|---|
| 01 | Character created | 9 | Equipment: Long Sword + Knight Shield + full Knight armor set (6/6 named) |
| 04 | Iudex Gundyr defeated | 9 | Soul count jumped +3,000 ✓ |
| 11 | Tower on the Wall bonfire lit | 9 | Bonfire ID 3000 = High Wall of Lothric ✓ |
| 12 | Leveled up to 13 | **13** | Shield unequipped, souls spent on 4 levels |
| 14 | Greirat freed | 13 | Blue Tearstone Ring appears in inventory ✓ |
| 15 | Emma talked to | 13 | Way of Blue appears in inventory ✓ |
| 16 | Vordt defeated | 13 | Soul of Boreal Valley Vordt in inventory ✓ |
| 18 | Foot of the High Wall bonfire | 13 | Bonfire ID 3100 ✓ |

### Three items shipped this session

**1. `BONFIRE_NAMES` extended** (`parser/userdata.py`):
Added confirmed IDs (3000 High Wall of Lothric, 3100 Foot of the High Wall) plus estimated IDs for all base-game and DLC areas from the `XXYY` area-numbering pattern.

**2. Way of Blue covenant badge added to `data/_ring.json`**:
`"Way of Blue": "4C 27 00 20"` (item_id `0x2000274C`). Confirmed from step-15 QA save.

**3. `parser/equipment.py` — equipment slots reader**:
New module. Reads currently-equipped weapons, armor, and rings from fixed offsets relative to `name_offset`:

```
name+492  left-hand weapon / shield (slot A)
name+496  right-hand weapon         (slot A)
name+540  head armor
name+544  chest armor
name+548  hand armor
name+552  leg armor
name+556  ring slot 1
name+560  ring slot 2
name+564  ring slot 3
name+568  ring slot 4
```

Armor item IDs in the equipment region use high byte `0x01` regardless of canonical `0x1X` category byte — module builds a reverse lookup keyed on lower 3 bytes. Empty sentinels: `0xFFFFFFFF`, `0x00000000`, `0x0001ADB0`.

Wired into `SlotSummary` (`equipment: List[EquipmentSlot]` field) and surfaced in `extract.py`.

**Result**: fresh characters no longer show empty inventory. QA step-01 now surfaces Long Sword + Knight Shield + Knight armor set.

---

## Session 4 — 40-save QA corpus + event-flag investigation (2026-05-29)

### 40-save QA corpus — full validation pass

Extended QA corpus from 20 to 40 saves (steps 21–40, through Undead Settlement / Firelink catch-up). All 40 saves parsed without errors.

### Two parser fixes this session

**1. Key items section discovered and implemented** (`parser/inventory.py`):
- DS3 stores key items in a **second 16-byte inventory grid at `name_offset + 0x7AA8`** (fixed, confirmed across all 40 QA saves).
- The two grids are separated by ~200 sentinel zero-records. The old 64-sentinel stop threshold halted before reaching key items.
- Fix: `parse_inventory` now calls `_scan_grid` twice and concatenates results.
- Impact: Cell Key, Small Lothric Banner, Grave Key, Loretta's Bone, Mortician's Ashes, Transposing Kiln, Estus Shard, Dark Sigil — all now surfaced.

**2. Covenant ring IDs added** (`data/_ring.json`):
- Mound-makers confirmed: `0x20002742` (appears at step 32, Hodrick gives it).
- Warriors of Sunlight, Blue Sentinels, Watchdogs of Farron, Aldrich Faithful, Rosaria's Fingers, Blade of the Darkmoon: estimated from cluster pattern, unconfirmed.

### Event-flag encoding — major investigation (2026-05-29)

**What we learned about where flags are NOT:**
- Entry 11 (13.4MB compressed) is the **schema** only — flag IDs as u32 LE in constant-context records, **identical across all saves** (0 bytes differ). It's a reference/dictionary, not the value store.

**What we learned about where flags ARE:**
- Flag values are stored in the slot payload, somewhere in the clean middle `0xD000–0x73000`.
- When a new flag is SET, an isolated `0x00 → single-bit` change appears in that region.

**Specific isolated flag signals observed:**
| Event | Byte(s) | Change |
|-------|---------|--------|
| Greirat sent to scavenge | `0x51CCA` | `0x00→0x04` |
| Talk to Irina in Firelink | `0x51CE1`, `0x51CFB` | `0x00→0x20`, `0x00→0x02` |
| Dark Sigil (Yoel draw) | `0x231D8`, `0x330E5`, `0x4C80E`, `0x51D04` | various single bits |

**(These absolute positions are from the specific save; they drift with `name_offset` — absolute addressing was found to be incorrect in later sessions.)**

**What's still unresolved after this session:**
- The hash function mapping flag_id → table_position (wrong hypothesis at this stage — see sessions 5–7).
- The ACTUAL BOSS-KILL flag bits — boss kills change many bytes (~7148 diffs for Iudex kill), making individual bits hard to isolate.

---

## Session 5 — Flag structure investigation (2026-05-29)

**Hypothesis: group directory + bit blocks.** (THIS MODEL WAS WRONG — retracted in session 6.)

Wrote investigation tooling (all in `scripts/`):
- `verify_flag_formula.py` — reads a flag's on/off timeline across the corpus.
- `diff_flags.py` — diffs two saves' flag region relative to the anchor.
- `find_monotonic_flags.py` — derives positional-index → event table from strictly-monotonic bits.
- `find_flag_anchor.py` — locates a sorted index in the slot payload. **(Session 6 clarification: this locates an INVENTORY structure, not event flags. Deprecated for flag work.)**

The "group directory + BPB" model appeared promising because monotonic bit analysis found bits that correlated with events — but the correlation was coincidental (inventory item additions, not flag sets).

---

## Session 6 — Controlled saves; session 5 model retracted (2026-05-30)

Ran 3 clean controlled pairs (fresh char **QA2, slot 5**): Talk-to-Greirat (01→02), Talk-to-Cornyx (03→04), Talk-to-Irina (05→06), in `controlled_saves/`. The Greirat pair is the gold standard — **identical `name_offset`, no inventory/level change** — so its byte diff is the cleanest possible.

**Session 5's "group directory + bit blocks" model was WRONG — retracted.** The `(key, index)` table that `find_flag_anchor.py` locates at ~`name+0x115A8` is **inventory/equipment data, not event flags**: bytes right after it decode as item IDs (Fire Arrow, etc.) then float physics data.

**What the clean Greirat diff actually shows (whole slot payload):**
- Two churn regions rewrite every save regardless: front `0x0–0xD000` (item-registry instance data) and back `0x73000–0xBF000` (float physics/position/camera).
- The **clean middle `0xD000–0x73000`** holds the real flags. "Talk to Greirat" set exactly three isolated `0x00 → single-bit` flags there: `0x1F2AF` bit 3, `0x2A9FD` bit 0, `0x344EF` bit 7 (absolute offsets; this save's `name_offset` = 0xCF84).

**Still-open hard problem after session 6:** Those bits are real flags, but reading them in other pairs (different `name_offset`) returns 0 — they are NOT at a simple `name + constant`. The flag section's anchor drifts non-uniformly with the variable item registry.

**Recommendation from session 6**: Stop pure black-box diffing. Consult DSMapStudio / alfizari editor source for a canonical DS3 slot-payload section map.

### Parser coverage validated against the 40-save corpus (post-session 6)

**The snapshot parser + consecutive-save diff already covers ~26 of 40 first-playthrough milestones**:

Events derivable purely by diffing consecutive snapshots:
- **Boss kills** — boss soul appears (step 04 Iudex via Coiled Sword, 16 Soul of Vordt, 33 Soul of Greatwood).
- **Key-item pickups / consumption** — 13 Cell Key, 21 Loretta's Bone, 30 Grave Key, 32 Estus Shard, 33 Transposing Kiln, 10 −Coiled Sword (planted), 36 −Loretta's Bone (given to Greirat).
- **NPC recruit gifts** — 14 Blue Tearstone Ring (Greirat), 15 Small Lothric Banner (Emma), 38 Pyromancy Flame (Cornyx).
- **Covenant joins** — 32 Mound-makers (Hodrick). **Ending signals** — 40 Dark Sigil (Yoel). **Location moves** — last-bonfire transitions. **Level-ups**.

The **~14 "silent" steps** (no inventory/bonfire change) are exactly the flag-only events: pure NPC-dialogue milestones and in-area bonfire lightings.

---

## Session 7 — Flag bitfield cracked; EMEVD sourced (2026-05-30)

**The event-flag bitfield is confirmed at `name_offset + 0x11660`.** *(Session 9 correction: this is wrong — see session 9.)*

### How FLAG_START_REL = 0x11660 appeared established (session 7 — later invalidated)

Monotonic bit scan across all 40 QA saves in **name_offset-relative** space (not absolute). Session-4 positional indices 29064 and 34127 mapped to `rel_pos - 0x11660` in the relative bitfield, matching expected steps. Verified against 4 independent events — all appeared monotonically correct. **This was a false positive — those bits were the item registry, not flags. See session 9.**

### Three-flag-system architecture (correct — validated by session 9)

DS3 saves contain **three separate flag stores**, not one:

| System | Location | What sets them | Example IDs |
|---|---|---|---|
| **EzState dialogue flags** | `name_offset + FLAG_START_REL` (flat bitfield) | NPC dialogue .esd scripts | 29064, 34127, 26203 |
| **EMEVD boss defeat flags** | Unknown (different region) | `SetEventFlag` in .emevd | 6319 (Iudex), 6301 (Vordt), 6303 (Greatwood) |
| **NPC state machine flags** | Unknown (different region) | `SetNetworkconnectedEventFlag` | 1421 (Greirat recruited), 1463 (Irina at Firelink) |

The EzState flags are what the bitfield at `name + FLAG_START_REL` stores. The boss defeat and NPC state-machine flags live in a different region — location still unknown.

### EMEVD sourced from DSMapStudio (m40, m30, m31, common)

- **Boss defeat flags**: 6319 Iudex, 6301 Vordt, 6302 Dancer, 6300 Consumed King, 6303 Greatwood, 6320 Champion Gundyr.
- **NPC quest state machine ranges**: Greirat 1420–1439 (1421=recruited, 1438=dead), Yoel 1040–1059, Yuria 1060–1079, Cornyx 1100–1119 (1101=at Firelink), Irina 1460–1479 (1463=at Firelink, 1478=hostile), Siegward 1300–1319, Hawkwood 1020–1039, Orbeck 1180–1199, Sirris 1200–1219, Leonhard 1360–1379, Karla 1240–1259, Patches 1260–1279, Eygon 1340–1359 + 1480–1499.
- Stored in `data/_emevd_flags.json`.

### BonfireWarpParam data (from DSMapStudio export)

- **`BONFIRE_NAMES` corrected** — previous area estimates were wrong. Correct formula: `WarpEventId // 10000 * 10 = area_code`.
- **`data/_bonfire_flags.json`** — 81-entry `LocationEventId → bonfire name` dictionary (complete base game + DLC).

### New files shipped this session

| File | Purpose |
|---|---|
| `parser/flags.py` | Flag reader: `read_flag(payload, name_offset, flag_id)`, `KNOWN_FLAGS` dict |
| `data/_bonfire_flags.json` | 81 LocationEventId → bonfire name (from BonfireWarpParam) |
| `data/_emevd_flags.json` | Boss defeat IDs + NPC state ranges from EMEVD |
| `scripts/find_flag_start.py` | Monotonic bit scanner that (incorrectly) located FLAG_START_REL |
| `scripts/diff_controlled_saves.py` | Diffs controlled save pairs by flag_id (handles name_offset drift) |
| `scripts/parse_emevd_flags.py` | Extracts SetEventFlag calls from decompiled EMEVD |
| `scripts/validate_flags_qa.py` | Validates KNOWN_FLAGS against all 40 QA saves |
| `extract.py` | Now outputs `flags_set` per slot (human-readable flag labels) |

---

## Session 8 — Advisor system + play simulator (2026-05-30)

### Play simulator (`play_simulator.py`)

Standalone script that replays a folder of numbered `.sl2` saves in sequence:

```
python play_simulator.py play_00          # 40-step QA playthrough
python play_simulator.py play_01          # 6 controlled save pairs
python play_simulator.py play_00 --interval 3   # 3s between steps
python play_simulator.py play_00 --no-tips      # diff only, no advisor
```

Key features:
- **Auto slot detection**: compares saves 1 and 2 to find which slot's playtime changed, then locks that slot for the whole run.
- **State diff output**: level-ups, location changes, soul gains/losses, inventory in/out, named flag milestones — zero LLM tokens.
- **Advisor integration**: after each diff, matched tips are shown only when the tip set changes. `[done]` printed when a tip exits scope.

Save folders live in `play_simulator_save_files/`:
- `play_00/` — 40-step QA playthrough (steps 01–40, slot 4)
- `play_01/` — 6 controlled save pairs (slot 5 / QA2)

### Rule-based advisor (`advisor.py` + `data/tips.json`)

**Architecture: zero LLM tokens at runtime.** Tips are structured rules in `data/tips.json`; `get_tips(state)` does pure Python condition matching.

Current tip database: 23 tips covering Cemetery of Ash → Undead Settlement, sourced from FightinCowboy 100% walkthrough transcript. Validated output — tips fire at exactly the right steps with no false positives across all 40 QA saves and 6 controlled saves.

### New files shipped this session

| File | Purpose |
|---|---|
| `play_simulator.py` | Active-play replay: copies each numbered save → parses → diffs → shows tips |
| `advisor.py` | `get_tips(SlotState) -> list[tip]`, `format_tips()` — zero tokens at runtime |
| `data/tips.json` | 23 hand-authored tips with trigger conditions |
| `sim_workspace/` | Working directory for the simulator's current save copy |

---

## Session 9 — FLAG_START_REL was wrong all along (2026-05-31)

### Core discovery: FLAG_START_REL = 0x11660 is the item registry, not flags

`name_offset + 0x11660` is the **item registry** — a sorted list of item IDs the character has ever acquired. When the monotonic analysis in session 7 found "flags" at positional indices like 29064, we were observing items being added to this sorted list, not event flags being set. **All KNOWN_FLAGS entries derived from that analysis have wrong labels.**

This explains:
- Why `diff_controlled_saves.py` showed 2385 changes between quest-track saves 05 and 07.
- Why flag 29064 read 0 in save 35 even though inventory confirmed the bone was already given.
- Why "very high" flag IDs (1.5M+) appeared in diffs.

### Actual flag bitfield location

The real EzState event flag bitfield starts at approximately:

```
name_offset + 0x403F4   (QA character, slot 4)
name_offset + 0x403F8   (Greirat character, slot 5)
```

**How confirmed**: clean same-name_offset diffs on QA corpus saves 35, 36, 37 (all `name_offset = 0x10AA0`):

| Event | abs position | byte change | bits set |
|-------|-------------|-------------|----------|
| loretta_bone_given (save 35→36) | 0x51CC5 | 0x00→0x0C | bits 2,3 |
| greirat_sent (save 36→37) | 0x51CC5 | 0x0C→0x0F | bit 0 added |
| greirat_sent secondary (36→37) | 0x51CCA | 0x00→0x04 | bit 2 |

With `FLAG_START_ABS = 0x10AA0 + 0x403F4 = 0x50E94`: byte offset in bitfield = 0x51CC5 - 0x50E94 = **3633**. Flag IDs in byte 3633: 29064 (bit 0), 29066 (bit 2), 29067 (bit 3).

Independently confirmed via greirat-quest controlled saves (slot 5, `name_offset = 0x11E88`): loretta_bone change at abs=0x530B1, which with `FLAG_START_REL = 0x403F8` also gives byte 3633.

### Corrected flag assignments

| Flag | Old label (WRONG) | Correct label |
|------|------------------|---------------|
| 29064 | "Loretta's Bone given to Greirat" | `greirat_sent_undead_settlement` (fires step 37) |
| 29066, 29067 | (unlabeled) | `loretta_bone_given` (bits 2,3 of byte 3633, fire step 36) |
| 34127 | "Greirat sent to scavenge" | **DISCARD** — derived from wrong FLAG_START_REL |

All other KNOWN_FLAGS from the QA corpus monotonic analysis need re-derivation.

### The 4-byte discrepancy

FLAG_START_REL = `0x403F4` for QA character (slot 4), `0x403F8` for Greirat character (slot 5). Cause unknown. Next step: compare both characters' payloads at `name_offset + 0x403F0` to `+0x403FC` in the same DS30000.sl2.

### Greirat-quest controlled save series

Location: `play_simulator_save_files/greirat-quest/`. Character: slot 5, name = "Greirat"

| Save | name_offset | Notes |
|------|-------------|-------|
| 01 - Cell Key in hand | 0x10C0C | Before opening cell |
| 02 - Greirat freed, BTR received | 0x11E88 | BTR added; name_offset jumps +0x127C |
| 03 - DS30000.sl2 | 0x11E88 | Area reload, Greirat at Firelink |
| 04 - Loretta Bone in inventory | 0x11E88 | Bone in bag, not yet given |
| 05 - Loretta Bone given | 0x11E88 | Bone removed from inventory (confirmed) |

Saves 02–05 all share name_offset 0x11E88 — clean for absolute diffs.

Flag 1425 (EMEVD NPC state range 1420–1439, Greirat's block) was set during the s03→s04 transition. Meaning unknown but candidate for area-visit or Greirat state flag.

### New script this session

`scripts/diff_greirat_quest.py` — diffs any two greirat-quest saves (slot 5, hardcoded), shows zone labels and checks for expected flags. Currently uses wrong FLAG_START_REL — **update after fixing FLAG_START_REL in `parser/flags.py`**.

### What needs fixing (action items)

1. **`parser/flags.py`**: change `FLAG_START_REL = 0x11660` to `0x403F4` (after resolving 4-byte issue). Replace all `KNOWN_FLAGS` with correctly labelled IDs.
2. **`decision_making_files/greirat_of_the_undead_settlement.json`** `flag_registry`:
   - `loretta_bone_given.id`: change from 29064 → **29066** (or add both 29066 and 29067)
   - `greirat_sent_undead_settlement.id`: change from 34127 → **29064**
3. **Re-run `scripts/find_flag_start.py`** on `play_simulator_save_files/play_00/` to re-derive all KNOWN_FLAGS.

---

## Session 10 — Event flags CRACKED: structural walk + semantic IDs (2026-06-11)

**The blocker is gone.** NPC quest events (the entire reason for the project) now
read from saves portably across characters with semantic flag IDs.

### Why everything before failed

The `find_bit_blocks_start()` content scan (session 9's fix) was locating the
**acquired-item index** at `name+0x11678` — the same structure session 6 had
already disqualified. Its 4 KNOWN_FLAGS were raw bit offsets from that anchor:
they fired on the characters they were calibrated on (quest-track) and stayed
silent on others (greirat-quest). Diffing also showed the real flag region
**slides as a unit**: +0x127C when the gaitem registry grows, +0x1C when the
acquired-item index grows (with no name_offset change) — no name-anchored or
content-scanned constant could ever be portable.

### The two keys

1. **alfizari's save editor** (`parse_save()` in main_ds3.py) walks the slot
   payload structurally — gaitem registry (variable), fixed blocks, two counted
   tables — landing on `event_flag_start`, a FIXED 0x33E5E-byte section.
2. **The TGA cheat table** hardcodes 156 in-memory world-flag (offset, bit)
   pairs. Every alfizari distance = TGA offset + 0x6F ⇒ the save section at
   `event_flag_start + 0x5D` is a byte-for-byte copy of the in-memory blob at
   `[[SprjEventFlagMan]+0]`.

From the CT data the codec fell out: flag `T AABB CCC(C)` → region origin by
type (1=event 0xF00, 6=object 0x1FE00, 7=talk 0x2A300) + map slot × 0x500 +
u32-LE MSB-first bit packing. Commons (ids < 30720) at blob start. Full model
in [flag_research.md](flag_research.md).

### Validation

- `scripts/validate_flags_qa.py`: **0 failures, 41 flags × 40 saves** (play_00).
- Cross-character: same IDs decode from QA (slot 4), quest_track (slot 4,
  modded), Greirat (slot 5) — e.g. Loretta's Bone given = 74000300/301 on all.
- Independent label confirmation: 74000600 ("Talked to Yuria") and 74000850
  ("Talked to Leonhard") match the TGA cheat table's own labels exactly.

### Shipped

- `parser/flags.py` rewritten: `find_event_flag_start()` (structural walk),
  `find_flag_blob()`, `flag_offset()`/`decode_offset()` (semantic codec),
  `diff_flags()`, curated KNOWN_FLAGS (24 boss defeats + 17 quest/NPC flags).
- `play_simulator.py` / `watcher.py`: flag events via semantic set-diff (the
  raw_flagbytes positional scan is gone).
- `data/tips.json`: all 13 flag-triggered tips remapped to semantic IDs.
- `decision_making_files/*.json`: flag registries updated — Greirat
  (74000300/302, commons 1224→1225→1226 state machine, cell door 63000156),
  Irina/Eygon (73100100, 74000350, 73100300), Yoel/Yuria (74000400 sigil,
  1084→1085→1086, 1064→1065, 74000600).
- `scripts/diff_controlled_saves.py`, `scripts/diff_greirat_quest.py`:
  rewritten as semantic diff CLIs; `scripts/decode_flag_diffs.py`,
  `scripts/verify_alfizari_walk.py`: the discovery/verification harnesses.

### Simulator output now (quest-track corpus)

Step 04: "Vordt of the Boreal Valley defeated", "Talked to Yoel of Londor" ·
Step 07: "Loretta's Bone given to Greirat", "Yoel: Dark Sigil drawn" ·
Step 08: "Talked to Irina of Carim (sewer cell)", "Talked to Eygon of Carim" ·
Step 11: "Curse-Rotted Greatwood defeated", "Greirat sent to scavenge Undead
Settlement" · Step 12: "Talked to Yuria of Londor". All previously silent.

---

## Session 11 — Advisor refactored: hybrid deterministic engine + Claude agent (2026-06-11)

Rebuilt the advisor around the product philosophy: **don't pre-hint
everything; tell the player what they missed after they've moved past it,
and only warn ahead of time when a quest can break.**

### Architecture

```
save event -> snapshot.py (shared SlotSnap + diff)
           -> advisor_core.py (deterministic findings, zero tokens)
           -> gate: no new findings -> silence
           -> advisor_agent.py (Claude, tools over the deterministic code)
              fallback: no API key -> deterministic text
```

- `snapshot.py` — NEW: SlotSnap (now incl. stats), snap_slot, diff_events.
  Removed the duplicated copies from watcher.py and play_simulator.py.
- `data/checkpoints.json` — NEW, replaces tips.json. Every checkpoint has a
  policy: `retrospective` (fires only after progression passes the area),
  `proactive` (quest-break prevention, the only ahead-of-time class),
  `reactive` ("you have X, do Y"). Added `where` (how-to-go-back) text.
- `advisor_core.py` — NEW: progression high-water mark over an ordered area
  list, checkpoint evaluation, quest_evaluator integration (warnings + phase
  transitions), per-character SessionMemory (delivered-once dedupe), state
  summary / quest status / area checklist / wiki keyword search helpers.
- `advisor_agent.py` — NEW: Claude agent (`claude-opus-4-8`, tool_runner,
  cached system prompt). Tools: get_player_state, get_quest_status,
  get_area_checklist, search_wiki. Writes ≤2 short player-facing messages.
- `advisor.py` — REWRITTEN as the orchestrator (`AdvisorSession`). Old
  get_tips()/tips.json matcher retired (tips.json kept as reference).
- `watcher.py` — advisor wired in after each save event (LLM by default,
  `--no-llm` flag). `play_simulator.py` — advisor wired in (deterministic by
  default, `--llm` / `--no-advisor` flags). Both now print UTF-8.
- `decision_making_files/yoel_and_yuria_of_londor.json` — `yuria_active`
  phase now keyed on talk flag 74000600 (validated), shop proxy as fallback.

### Validation (quest-track corpus, deterministic mode)

- Step 01 (Firelink): Cemetery Crystal Lizard fires retrospectively — the
  exact "rested at the next bonfire" behaviour the product wants.
- Step 02 (High Wall): reactive "free Greirat" + proactive Emma + Firelink
  retrospectives; Yoel warning correctly absent until US.
- Step 04 (US): Hodrick + Giant Archer warnings, Loretta/Siegward steps,
  High Wall retrospectives. Yoel warning correctly suppressed (flag already
  set in that save — no false positive).
- Steps 05–11: Greirat/Irina/Yoel reactive steps and phase nudges track the
  questlines; everything fires exactly once (memory dedupe).
- Step 12: Yuria-active guidance with the three CRITICAL questline rules.
- pytest: 23 passed, 13 skipped (unchanged).

### Topic dedupe (same session, follow-up)

Live testing showed the same quest beat surfacing 2-3 times per save event
(checkpoint + quest warning + quest phase all describe "deliver Loretta's
Bone"). Added a `topic` key shared across checkpoints.json and the decision
files' phases/warnings: one finding per topic within a report (urgency wins,
checkpoint text preferred on ties), and delivered topics persist in session
memory so no source ever re-covers a beat. See
[advisor_and_tips.md → Topics](advisor_and_tips.md). Re-validated on
quest-track: step 05 now one Loretta message (was 3), step 07 one each for
Grave Key / first outing / Dark Sigil (was 5), step 04's "find Loretta's
Bone" correctly silent (covered by step 03's phase message).

### Notes / known gaps

- The LLM layer is untested against the live API in this session (no key in
  the dev shell) — fallback path verified instead.
- `advisor_memory/` is per-character persistent state, gitignored.
