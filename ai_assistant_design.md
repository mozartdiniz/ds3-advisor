# DS3 AI Companion — Design Notes

> **This file has been split into the `ai_assistant_design/` folder.**
> See [`ai_assistant_design/index.md`](ai_assistant_design/index.md) for the full index and quick-lookup table.

> ⚠️ **Everything below about event flags is OBSOLETE.** All flag models in this
> file (FLAG_START_REL 0x11660 / 0x403F4, the group-directory scan, the
> three-flag-store theory, all raw flag IDs like 29064/34127) were superseded on
> 2026-06-11 — flags are now read via a structural payload walk with semantic
> flag IDs. See [`ai_assistant_design/flag_research.md`](ai_assistant_design/flag_research.md).

---

*(Original monolithic content preserved below for git history — all content has been migrated to the split files.)*

---

Captured from initial scoping conversation. Living document — update as decisions change.

---

## Vision

A passive companion that watches a player's Dark Souls 3 save file and surfaces contextual guidance: lockout warnings, missable-content nudges, ending steering, build viability checks, and point-of-no-return checklists. The product is meant to *prevent regret* on a first or second playthrough, not to spoon-feed a guide.

Architecture summary (v0):

```
[Windows PC]                  [Home server: Linux/Mac on LAN]          [iPad / phone PWA]
 DS3 save (.sl2)               FastAPI + SQLite (FTS5)
      │                          │
      ▼                          ├─ /ingest   ◄── raw .sl2 (POST) ──┐
 watcher.py                      ├─ decrypt + parse                  │
 (mtime poll, ~2s)               ├─ diff vs prior state (SQLite)     │
      │                          ├─ rule engine (deterministic)      │
      └──── POST raw .sl2 ───────┤                                    
                                 ├─ LLM phrases fired rules           
                                 ├─ persist messages (+ FTS5 mirror)  
                                 │                                    
                                 ├─ /events    (SSE) ───────────►  chat feed
                                 └─ /history?since=...  ────────►  catch-up
```

Raw `.sl2` travels client→server in v0 — see "Architectural decisions made" for the rationale and when to revisit.

---

## Where we are — snapshot 2026-05-28

### Validation pass against `save_files/DS30000.sl2` (4-slot real player save)

Ran the parser against a real player save with 4 populated slots, then walked each slot with the user and validated against ground truth they hold in their head. Results:

| Slot | Name | Class | Lvl | Location | NG | Origin | Parser correct? |
|---|---|---|---|---|---|---|---|
| 0 | Dark Tarnished | Knight | 195 | The Ringed City | **NG+5** | played | ✅ all fields |
| 1 | Frederico | Knight | 171 | Firelink Shrine | NG 0 | item-modded | ✅ all fields |
| 2 | Melissa | Sorcerer | 159 | Kiln of the First Flame | NG 0 | item-modded | ✅ all fields |
| 3 | Clodoaldo | Knight | 9 | Cemetery of Ash | NG 0 | fresh (3min) | ⚠️ empty inventory — see below |

**Key validation wins:**
- Stat block, level, class, sex, playtime, souls — all correct across the four slots, including the multi-cycle Dark Tarnished (1,119-item NG+5 inventory) and the fresh Clodoaldo.
- Reasoner correctly flagged FAITH 40 + no chime on Melissa (a real "you forgot something" moment that the player confirmed they'd want surfaced).
- Reasoner correctly listed 16 unspent boss souls on Dark Tarnished and 3 on Frederico — counts cross-checked.
- Userdata-level vs slot-level always matched. The earlier screenshot showed lvl 181 for Dark Tarnished but the parser said 195 — turned out the screenshot was 9h older than the last save write; player kept playing.

**Major discovery: BND4 entry 11 is the event-flag store (and was never documented).**
- `DS30000.sl2` has **12 BND4 entries**, not 11. Entries 0–9 are slot payloads, entry 10 is userdata. **Entry 11 is 1 MB encrypted, and was completely uncharted before this session.**
- Entry 11 wraps a **DCX-DEFLATE compressed nested BND4**: outer 16-byte " GER" wrapper → standard DCX/DCS/DCP/DFLT header → zlib-DEFLATE stream → expands to **13.4 MB** containing 103 sub-entries (one per map area: first is `01350000` = Lothric).
- **Every wiki flag ID I tested is present as a u32 LE inside the decompressed payload.** Boss-dead flags (13000800 Vordt, 14100800 SoC, 15110800 Gael, etc.), boss-victory flags, covenant flags — all there.
- Encoding caveat: each flag ID appears in a constant-context record (prefix `00 00 00 00 23 bf 98 00`, suffix `ff ff ff ff 03 00 00 00 00 00 80 bf`) regardless of whether it's set. So these are **schema entries**, and the actual set/unset bit lives elsewhere in the payload — still to be decoded. The path is: two controlled saves with one known flag flipped, diff decompressed entry 11, find the value bit.
- Implication: this is the file the *whole* AI-companion design hinges on. Once the value-bit encoding is cracked, ~all NPC questline / lockout / ending rules become reachable.

**Event-flag dictionary scraped.**
- `scripts/scrape_event_flags.py` — DokuWiki HTML walker that pulls https://soulsmodding.com/doku.php?id=ds3-refmat:event-flag-list into `data/_event_flags.json`. 354 flags. CC BY-SA 4.0, attribution preserved in the JSON header.
- Coverage check: boss kills (all base + DLC), boss victory, covenant unlocks, NPC quest item drops (Cornyx, Karla, Irina, Eygon, Anri, Yuria, Greirat, Orbeck, Siegward, Sirris, Patches, Hawkwood, Leonhard, Shira, Sister Friede), crow trades, one-time loot drops. NPC dialogue exhaustion *per se* isn't deeply cataloged — but quest-step milestones ("Yuria gave Morion Blade", "Siegward gave Storm Ruler at Yhorm") are, which is what we actually need for prevent-regret rules.
- Known limitation: scraper currently lumps everything under the page title `Event Flags (DS3)` instead of the proper subsections. Tracked as a follow-up — IDs and labels are correct.

**New parser field landed: `last_bonfire_id` + `last_bonfire_name`**
- Lives in **userdata** (BND4 entry 10), per-slot record at byte offset **+50, u16 LE**. Not in the slot payload itself — the load-screen reads it from here, which is why it varies even when the slot's own "current world position" doesn't.
- Found by diffing the 4 slot records (stride 554) for u16 LE offsets with 4 distinct values in a small magnitude range. Only one offset matched cleanly: +50.
- Confirmed 4-digit IDs, BonfireWarpParam-like:
  - 4000 → Cemetery of Ash
  - 4005 → Firelink Shrine
  - 4100 → Kiln of the First Flame
  - 5100 → The Ringed City (DLC2)
- Resolved via a small `BONFIRE_NAMES` dict in `parser/userdata.py` — easy to extend as more saves arrive. Unknown IDs surface as `last_bonfire_id` set, `last_bonfire_name = None`.
- Pinned in `tests/test_bonfires.py` (4 cases). The previous "Last bonfire — probed but unresolved" pending item in this doc is now resolved.

**New parser-correctness finding (slot 3, Clodoaldo):**
- The inventory parser only walks the 16-byte **inventory grid** at `name_offset + 996`. That grid holds consumables, key items, spells, rings, ammo — i.e. the *non-upgradeable* stuff.
- Upgradeable items (weapons, armor, rings-as-instances) live in the **item registry** at `0x60` onwards, as 60-byte records. The design doc already noted the registry exists; it just isn't iterated.
- For stocked characters the grid is huge anyway, so missing the registry isn't visible. But for **fresh characters whose only possessions are the starting class gear** (Clodoaldo: Knight Shield, Knight Helm/Armor/Gauntlets/Leggings — all found at `0x42a8`–`0x44c4`, plus Longsword), the parser reports zero items.
- Estus Flask is *not* an inventory item — it's a separate flask-count system tied to bonfires. So a fresh Knight with starting gear and 4 Estus genuinely has zero grid records.
- **Action**: add registry iteration to the inventory module (or as a sibling `equipment.py`), surfacing each owned upgradeable instance with handle / item_id / count / durability. This also unblocks the "still to map" item about *currently-equipped* slot handles, since those handles point into the registry we'd now be walking.

### Session 3 work — 2026-05-28 (continued)

#### 20-save QA corpus — full validation pass

Created 20 sequential save files in `save_files/` (named `01_created_character_nothing_done.sl2` → `20_Light_the_Undead_Settlement_Bonfire.sl2`). Each captures one key event in a fresh Knight playthrough ("QA", slot 4). Saves are cumulative — each contains all prior progress. Parsed all 20 with the updated parser and validated against the recorded event sequence:

| Step | Event | Lvl | Key validation |
|---|---|---|---|
| 01 | Character created | 9 | Equipment: Long Sword + Knight Shield + full Knight armor set (6/6 named) |
| 02-03 | Ashen Estus looted, Cemetery bonfire lit | 9 | Souls accumulating from enemies |
| 04 | Iudex Gundyr defeated | 9 | Soul count jumped +3,000 ✓ |
| 05-10 | Firelink Shrine, various NPCs | 9 | Bonfire ID 4005 = Firelink Shrine ✓ |
| 11 | Tower on the Wall bonfire lit | 9 | Bonfire ID 3000 = High Wall of Lothric ✓ |
| 12 | Leveled up to 13 | **13** | Shield unequipped, souls spent on 4 levels |
| 14 | Greirat freed | 13 | Blue Tearstone Ring appears in inventory ✓ |
| 15 | Emma talked to | 13 | Way of Blue appears in inventory ✓ |
| 16 | Vordt defeated | 13 | Soul of Boreal Valley Vordt in inventory, souls +3,000 ✓ |
| 18 | Foot of the High Wall bonfire | 13 | Bonfire ID 3100 = Foot of the High Wall ✓; Long Sword now +1 (0x001EAB91 — unnamed: plain reinforcement levels absent from alfizari map) |
| 20 | Undead Settlement bonfire | 13 | Still at 3100 (character had not rested at Settlement interior bonfire yet) |

All 20 saves parsed without errors. No validation failures.

#### Three items shipped this session

**1. `BONFIRE_NAMES` extended** (`parser/userdata.py`):

Added confirmed IDs (3000 High Wall of Lothric, 3100 Foot of the High Wall) plus a full set of estimated IDs for all base-game and DLC areas, derived from the `XXYY` area-numbering pattern. Confirmed empirically: 3000, 3100, 4000, 4005, 4100, 5100 (The Dreg Heap — first bonfire of the Ringed City DLC). All others are best-effort estimates; extend from controlled saves as needed.

**2. Way of Blue covenant badge added to `data/_ring.json`**:

`"Way of Blue": "4C 27 00 20"` (item_id `0x2000274C`, ring category). Confirmed from step-15 QA save. Other covenant badges need empirical confirmation before addition.

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

Key encoding quirk: armor item IDs in the equipment region use high byte `0x01` regardless of the canonical `0x1X` category byte in the armor map. The module builds a reverse lookup keyed on the lower 3 bytes to bridge the gap. Shields (high byte `0x01`) appear identically in both the slot and the weapon map — looked up directly. Empty sentinels: `0xFFFFFFFF`, `0x00000000`, `0x0001ADB0`.

Wired into `SlotSummary` (new `equipment: List[EquipmentSlot]` field) and surfaced in `extract.py` as an `"equipment"` key alongside `"inventory"` (empty slots are omitted from the JSON output).

**Result**: fresh characters no longer show an empty inventory. QA step-01 now surfaces Long Sword + Knight Shield + Knight helm/armor/gauntlets/leggings from the equipment region.

---

### Snapshot from 2026-05-27

**Working POC pipeline**, run from `ai_assistant/`:

```
python extract.py <save.sl2>          → writes state.json next to the save
python reason.py  <state.json>        → prints advice grouped by slot
python -m parser.cli <save.sl2>       → tabular summary, no JSON
pytest tests/                         → 9 passing, 13 skipped (corpus saves not on disk)
```

### File map

```
dark-souls/  (repo root)
├── DS30000.sl2                       canonical "Wanderer mule" test save (10 slots populated)
├── ai_assistant_design.md            this doc
├── save_files/                       saves used for validation
│   ├── 01_created_character_nothing_done.sl2   QA playthrough step 1
│   ├── … (20 sequential QA saves, steps 01–20)
│   ├── max_level_and_new_game_plus_5/    "1205" lvl 802 NG+5 / 603M souls; bonus "1146" lvl 20
│   ├── sl_715/                            "Morguls" SL715, 99 in 8 attrs + LCK 12, Knight
│   └── the_usurpation_of_fire_ending/     "Male Hero 1" lvl 204 Deprived
└── ai_assistant/
    ├── pyproject.toml                  pycryptodome + pytest, Python 3.9+
    ├── venv/                           local virtualenv
    ├── extract.py                      CLI: save → state.json (includes equipment)
    ├── reason.py                       CLI: state.json → advice  (5 rules so far)
    ├── parser/
    │   ├── bnd4.py                     BND4 container reader
    │   ├── crypto.py                   DS3 AES-CBC key + decrypt
    │   ├── userdata.py                 reads BND4 entry 10 (load-screen index, occupancy, bonfire)
    │   ├── slots.py                    per-slot parsing, dynamic name anchor
    │   ├── stats.py                    9 attributes + level + souls (relative to name)
    │   ├── inventory.py                16-byte grid parser, ID→name resolution
    │   ├── equipment.py                equipment slots reader (weapons, armor, rings — relative to name)
    │   └── cli.py                      `python -m parser.cli`
    ├── data/
    │   ├── _weapons.json               weapon ID→name (alfizari)
    │   ├── _armor.json                 armor ID→name (alfizari)
    │   ├── _ring.json                  ring ID→name (alfizari + Way of Blue added)
    │   ├── _goods_magic.json           consumables + spells ID→name (alfizari)
    │   └── _event_flags.json           354 event flag IDs→labels (soulsmodding.com, CC BY-SA 4.0)
    ├── scripts/                        one-off probes used to discover offsets
    ├── tests/
    │   ├── test_slots.py               9 tests anchored on Wanderer save — all passing
    │   ├── test_save_corpus.py         parametrised across 3 corpus saves (13 skipped, saves not on disk)
    │   └── test_bonfires.py            bonfire ID resolution (skipped, corpus saves not on disk)
    └── (controlled save pairs live in play_simulator_save_files/, e.g. play_01/)
```

### What the parser extracts today (per slot)

- name, character class (Knight / Mercenary / Warrior / Herald / Thief / Assassin / Sorcerer / Pyromancer / Cleric / Deprived), sex
- level, playtime (ms precision), souls
- 9 attributes (VIG, ATT, END, VIT, STR, DEX, INT, FTH, LCK)
- last bonfire rested at (ID + human-readable name, resolved from `BONFIRE_NAMES`)
- **equipment loadout**: left/right hand weapons, head/chest/hands/legs armor, ring slots 1–4 — item ID + resolved name for each non-empty slot
- inventory grid: every non-upgradeable item (consumables, key items, spells, rings, ammo) with category, item ID, count, resolved name
- occupancy for all 10 character slots (which are populated)

**Gap**: owned weapons/armor that are neither equipped nor in the inventory grid (e.g. stashed extras) are not yet surfaced. The item registry (60-byte records before `name_offset`) covers those — see "Still to map".

### What the reasoner does today (10 rules — Session 5 expanded the set)

All single-state predicates over reliably-parsed data (stats, inventory, equipment, last bonfire) — no event flags needed. Regression-tested in `tests/test_reason.py` (crafted slot dicts, no corpus saves required).

- `E.int_no_catalyst` — INT ≥ 14 with no staff in inventory
- `E.faith_no_chime` — FAITH ≥ 14 with no chime/talisman in inventory
- `E.caster_no_flame` *(new)* — INT ≥ 12 **and** FAITH ≥ 12 (pyromancy spread) but no flame/staff/chime owned → point at Cornyx's free Pyromancy Flame
- `E.low_vigor` *(new)* — level ≥ 25 and VIG < 18 → fragility nudge
- `E.stat_overinvest` *(new)* — any attribute past its effective ceiling (STR/DEX/INT/FTH/LCK 60, VIG 50, END 40) → wasted-points info
- `E.ludleth_trades_available` — list unused boss souls + their Ludleth trade options
- `F.covenant_badges` *(new)* — report covenant badges owned (Way of Blue, Mound-makers, etc.) and how each works
- `H.key_item_nudges` — tips for Loretta's Bone, Small Doll, Eyes of a Fire Keeper, Storm Ruler, Dark Sigil, Pale Tongue, Old Cell Key, **Transposing Kiln, Grave Key** *(new)*
- `H.area.<area>` *(new)* — last-bonfire-keyed missable/lockout nudges for 11 base-game areas (Firelink, High Wall, Undead Settlement, Road of Sacrifices, Cathedral, Farron, Catacombs, Irithyll, Profaned Capital, Lothric Castle, and a **Kiln point-of-no-return checklist** that fires as a `warning`)
- `D.usurpation_path_active` — Dark Sigil present → flag that Yoel/Yuria path is active (imprecise without hollowing count)

The "1146" save (a side character on the max_level file: lvl 20 with INT 15 / FAITH 22 and no caster gear) triggers genuine prevent-regret advice — this is the first concrete proof the pipeline produces useful output.

### Key decisions made this session

- **Architecture pivot to POC.** Deferred the full server + watcher + PWA stack from the design doc. POC is just two Python CLIs that read/write JSON. Server/watcher/PWA stay in the design doc as the v1 target, but iterating on parser + rules content doesn't need them.
- **Dynamic name offset.** Hard-coded `0x019FEC` for the name only worked on the Wanderer mule save (because all 10 of its slots have identically-sized item registries). Real saves have variable-size registries that push the name to anywhere from `0x150E8` to `0x27534`. Fix: use the name from `userdata` (entry 10) as a needle, search the slot for it, anchor every other offset relative to that position. All offsets in `stats.py` and `inventory.py` are now stated as deltas from `name_offset`. Mirrors what `souls_givifier` does.
- **Sex is 1 byte at name+34, not 2.** Earlier `u16 == 0x0101 = 257` for sl_715/Usurpation was actually `u8 sex=1 + u8 age-or-bodytype=1`. Sex: 0=Female, 1=Male.
- **Playtime: u32 LE milliseconds at slot payload offset 8.** More precise than the user-data version (which is rounded to seconds). Cross-checked against load-screen timestamps for all 10 Wanderer slots — match exactly.
- **Inventory grid: starts at `name_offset + 996`**, 16-byte records, item_id at +4 (high byte = category), count at +8. Internal sentinel gaps up to ~26 records between sub-sections; real end is a much longer (1,200+) sentinel run. Threshold of 64 distinguishes.
- **Equipment region (`0x60 – 0x019F00`) is an item registry**, not equipped items. 60-byte records, one per upgradeable owned instance, with durability at +8. Currently-equipped items are a *separate* list of handles pointing into this registry — not yet located.

### Session 4 work — 2026-05-29

#### 40-save QA corpus — full validation pass

Extended QA corpus from 20 to 40 saves (steps 21–40, through Undead Settlement / Firelink catch-up). See full event detection table in the project memory file.

#### Two parser fixes this session

**1. Key items section discovered and implemented** (`parser/inventory.py`):
- DS3 stores key items (keys, ashes, quest items, story flags) in a **second 16-byte inventory grid at `name_offset + 0x7AA8`** (fixed, confirmed across all 40 QA saves).
- The two grids are separated by ~200 sentinel zero-records. The old 64-sentinel stop threshold halted before reaching the key items.
- Fix: `parse_inventory` now calls `_scan_grid` twice and concatenates results.
- Impact: Cell Key, Small Lothric Banner, Grave Key, Loretta's Bone, Mortician's Ashes (and its disappearance when given to Handmaid), Transposing Kiln, Estus Shard, **Dark Sigil** — all now surfaced.

**2. Covenant ring IDs added** (`data/_ring.json`):
- Mound-makers confirmed: `0x20002742` (appears at step 32, Hodrick gives it).
- Warriors of Sunlight, Blue Sentinels, Watchdogs of Farron, Aldrich Faithful, Rosaria's Fingers, Blade of the Darkmoon: estimated from cluster pattern, unconfirmed.

#### Event-flag encoding — major investigation (2026-05-29)

**What we learned about where flags are NOT:**
- Entry 11 (13.4MB compressed) is the **schema** only — flag IDs as u32 LE in constant-context records, **identical across all saves** (0 bytes differ). It's a reference/dictionary, not the actual value store.
- Entry 11 tail (244KB after DCX blob) is all zeros.

**What we learned about where flags ARE:**
- Entry 4 (slot payload, 786,432 bytes) and entry 10 (userdata, 393,216 bytes) are **98% identical** for the first 393,216 bytes. Entry 10 is effectively the "inventory + state" half of slot 4's payload; the float/physics data (0x77000–0xBF000) is only in entry 4.
- Flag values are stored in a **sparse hash table with linear probing** in the slot payload, at absolute positions roughly 0x22000–0x56000.
- When a new flag is SET, the hash table inserts a new 8-byte record. Existing records that collide get displaced by exactly 8 bytes (the "swap pattern" visible in the Greatwood kill diff).
- A new flag's insertion appears as a NEW BYTE becoming non-zero (0→value) at a specific position, with no matching reverse change nearby.

**Specific isolated flag signals observed:**
| Event | Byte(s) | Change |
|-------|---------|--------|
| Greirat sent to scavenge | `0x51CCA` | `0x00→0x04` |
| Talk to Irina in Firelink | `0x51CE1`, `0x51CFB` | `0x00→0x20`, `0x00→0x02` |
| Dark Sigil (Yoel draw) | `0x231D8`, `0x330E5`, `0x4C80E`, `0x51D04` | `→0x20`, `→0x60`, `→0x20`, `→0x80` |

**The 0x51xxx region (NPC interaction log):**
- NOT a stable persistent flag store. The ~0x51B00–0x51E00 region behaves like a circular buffer of recent NPC interactions. When a large NPC event happens (talking to Cornyx at Firelink, save 38), the entire previous state clears and new state appears for the new NPC set.
- However, SOME bits persist across subsequent saves (e.g., `0x51CE1=0x20` from Irina persists through save 40). Not yet fully characterised.

**What's still unresolved:**
- The **hash function** mapping flag_id → table_position. Without it, we can't directly look up arbitrary flag IDs.
- Positions in the hash table (0x22000–0x50000) shift somewhat based on insertion order. For a canonical first-playthrough they should be stable, but differ for out-of-order playthroughs.
- The ACTUAL BOSS-KILL flag bits — boss kills change many bytes (Iudex kill: ~7148 diffs in 0x10000–0x60000), making the isolated flag hard to identify from the noise.

**Immediate practical path forward:**
- Build an empirical table: for each of the ~30 most critical events (boss kills, NPC recruitments, key quest steps), use controlled saves to find the specific byte positions that reliably change for that event.
- Start with `HAVE_KEY_ITEM` predicates (already working from inventory) + `BYTE_SET(offset, mask)` predicates for the specific positions found above.
- The hash function can be reverse-engineered by looking at more flag-insert events and finding the pattern. Candidate approach: examine a large-inventory save where many flags are set and look for the encoding.

### Session 5 work — 2026-05-29 (event-flag structure cracked open)

**The "hash table with linear probing" model from Session 4 was WRONG.** The flag region is a classic FromSoft **event-flag group directory + bit blocks**:

```
[ directory: sorted (group_key u16, block_index u16) pairs ][ bit blocks ]
```

- **Located by CONTENT, not a fixed offset.** `name + 0x11660` is NOT a stable anchor — a variable-size section sits between the name and the flag region, so the directory start drifts across saves (observed `name+0x115A8` … `name+0x11660` over the 40-save corpus). The reliable anchor is `scripts/find_flag_anchor.py:find_directory()`, which scans forward from the key-items grid for the start of the `block_index = 0,1,2,3,…` / strictly-increasing-`group_key` sequence. **Found correctly in all 40 saves** (always 41 entries for the QA character, max group_key 82).
- **The directory evolves as the player progresses.** 9 distinct directory contents across the 40 saves — new groups get allocated and the sorted order/`block_index` assignments reshuffle (e.g. key 10→11, 14→15). This reshuffling is exactly why absolute/positional offsets drift between saves.
- **Reading a semantic flag F:** `group = F // BPB`, `bit = F % BPB`; binary-search the directory for `group` → `block_index`; the bit lives at `blocks_start + block_index * BLOCK_BYTES + bit//8`, bit `bit % 8`. If `group` is absent from the directory, the flag is 0 (no block allocated).
- **The Session 4 "positional indices" (29064, 34085, 34127, 1564013) were raw `byte*8 + bit` offsets from `name+0x11660`**, conflating directory + block bytes. They correlated with events ONLY for the late, name_offset-stable saves where that anchor happened to be the directory start — they are NOT semantic flag IDs and break once the directory shifts. The `verify_flag_formula.py` "monotonic across all 40" result was a false positive: the pre-event saves read 0 simply because the wrong location is zero-filled.

**What's still open (the last mile):**
- **Exact `BPB` (block bit-capacity) + block byte layout.** `BPB=256` puts Iudex's "defeated" flag (wiki `6104`) first-ON at step 4 (correct!), but reads non-monotonic at a few saves and can't separate `6104` (Iudex) from `6105` (Vordt) — they fall in the same byte at BPB=256, and `6105` reads set too early. So BPB is probably finer, or blocks aren't simply contiguous in `block_index` order. **Next step:** two controlled saves differing by exactly ONE known wiki flag → find the single changed bit in the block region → back out `BPB` from `group = F // BPB` / `bit = F % BPB`. This solves it cleanly and unlocks the full 354-entry wiki dictionary.

Investigation tooling written this session (all in `scripts/`):
- `verify_flag_formula.py` — reads a flag's on/off timeline across the corpus (legacy direct-index; kept for reference).
- `diff_flags.py` — diffs two saves' flag region relative to the anchor; clean bitfield window is `[0, 0x34000)`, beyond is physics/world noise.
- `find_monotonic_flags.py` — derives an (positional-index → event) table from strictly-monotonic bits, labelled by save filename.
- `find_flag_anchor.py` — directory locator. **NOTE (Session 6): this locates an INVENTORY structure, not the flag store. Deprecated/misleading for flag work — see Session 6.**

### Session 6 work — 2026-05-30 (controlled saves; Session 5 model RETRACTED)

Ran 3 clean controlled pairs (fresh char **QA2, slot 5**): Talk-to-Greirat (01→02), Talk-to-Cornyx (03→04), Talk-to-Irina (05→06), in `controlled_saves/`. The Greirat pair is the gold standard — **identical `name_offset`, no inventory/level change** — so its byte diff is the cleanest possible.

**Session 5's "group directory + bit blocks + BPB" model was WRONG — retracted.** The `(key, index)` table that `find_flag_anchor.py` locates at ~`name+0x115A8` is **inventory/equipment data, not event flags**: the bytes right after it decode as item IDs (`400100` = Fire Arrow, `400101/2` = other arrows) then float physics data. The "new group 47" the Irina pair seemed to allocate was just **Soul of Boreal Valley Vordt added to inventory** on that boss kill — a new item-index entry, not a flag group. So the BPB hunt was chasing an inventory index.

**What the clean Greirat diff actually shows (whole slot payload):**
- Two churn regions rewrite every save regardless of action: front `0x0–0xD000` (item-registry instance data) and back `0x73000–0xBF000` (float physics/position/camera). Even "just talk to an NPC" rewrites ~316 KB here.
- The **clean middle `0xD000–0x73000`** holds the real flags. "Talk to Greirat" set exactly three isolated `0x00 → single-bit` flags there: `0x1F2AF` bit 3, `0x2A9FD` bit 0, `0x344EF` bit 7 (absolute offsets; this save's `name_offset` = 0xCF84).
- `0x53000–0x53430` and `0x555xx` also moved but as multi-byte float/circular-buffer churn (the Session-4 "NPC interaction log") — volatile, not stable flags.

**Still-open hard problem: portable addressing.** Those three bits are real flags, but reading them in the other pairs (different `name_offset`) returns 0 — so they are NOT at a simple `name + constant`, nor absolute. The flag section's anchor drifts non-uniformly with the variable item registry and is not yet pinned.

**Recommendation — stop pure black-box diffing.** Efficient path: consult a canonical DS3 slot-payload section map (**DSMapStudio / the alfizari editor source already cited**) for where the event-flag section starts and how it's addressed. For the *live product*, a pragmatic shortcut needs no global addressing: diff **consecutive** saves of one playthrough (where `name_offset` barely moves), scan the clean middle `0xD000–0x73000` for isolated `0→1` bit-sets, and treat each as "a flag fired"; the controlled pairs supply the labels.

#### Parser coverage validated against the 40-save corpus (post-Session-6)

Re-ran the current parser across all 40 `save_files/*.sl2` (QA, slot 4) to confirm what is reliably extractable *without* event flags. Conclusion: **the snapshot parser + a consecutive-save diff already covers ~26 of 40 first-playthrough milestones** — and most of the prevent-regret ones.

Reliable per-save current state (every file, no errors): identity (name/class/sex/level/playtime/souls), all 9 attributes, last bonfire (id+name), equipped loadout, full inventory **including the key-items grid**.

Events derivable purely by diffing consecutive snapshots:
- **Boss kills** — boss soul appears (04 Iudex via Coiled Sword, 16 Soul of Vordt, 33 Soul of Greatwood).
- **Key-item pickups / consumption** — 13 Cell Key, 21 Loretta's Bone, 30 Grave Key (−Mortician's Ashes), 32 Estus Shard, 33 Transposing Kiln, 10 −Coiled Sword (planted), 36 −Loretta's Bone (given to Greirat).
- **NPC recruit gifts** — 14 Blue Tearstone Ring (Greirat), 15 Small Lothric Banner (Emma), 38 Pyromancy Flame (Cornyx).
- **Covenant joins** — 32 Mound-makers (Hodrick). **Ending signals** — 40 Dark Sigil (Yoel). **Location moves** — last-bonfire transitions. **Level-ups** — souls/level deltas.

The **~14 "silent" steps** (no inventory/bonfire change) are exactly the flag-only events: pure NPC-dialogue milestones (07–09, 31 Talk-to-Irina, 37 Greirat-sent-to-scavenge, 39 Talk-to-Irina) and in-area bonfire lightings (17, 20, 22, 34). These are precisely what the unsolved flag region would unlock — and nothing else the parser already handles.

### Session 7 work — 2026-05-30 (flag bitfield cracked; EMEVD sourced)

**The event-flag bitfield is confirmed at `name_offset + 0x11660`.**

#### How FLAG_START_REL = 0x11660 was established

- Monotonic bit scan across all 40 QA saves in **name_offset-relative** space (not absolute — absolute scans failed because `name_offset` drifts 0xD1C0–0x11974 between saves).
- Session-4 positional indices 29064 (Loretta's Bone) and 34127 (Greirat scavenging) map exactly to `rel_pos - 0x11660` in the relative bitfield, matching the expected steps (36 and 37).
- Verified against 4 independent events (flags 29064, 34085, 34127, 34079) — all monotonically correct.
- **Controlled saves** (`controlled_saves/01–06`) provided the cleanest confirmation: 3 NPC pairs (Greirat, Cornyx, Irina) each showed flag changes at the expected bit positions.

#### Three-flag-system architecture (key finding)

DS3 saves contain **three separate flag stores**, not one:

| System | Location | What sets them | Example IDs |
|---|---|---|---|
| **EzState dialogue flags** | `name_offset + 0x11660` (flat bitfield) | NPC dialogue .esd scripts | 29064, 34127, 26203 |
| **EMEVD boss defeat flags** | Unknown (different region) | `SetEventFlag` in .emevd | 6319 (Iudex), 6301 (Vordt), 6303 (Greatwood) |
| **NPC state machine flags** | Unknown (different region) | `SetNetworkconnectedEventFlag` | 1421 (Greirat recruited), 1463 (Irina at Firelink) |

The EzState flags are what the bitfield at 0x11660 stores. These are NOT in any EMEVD script (searched m40, m30, m31, common.emevd, common_func.emevd — none contain SetEventFlag(29064) etc.). They are set by the NPC dialogue tree when specific dialogue nodes fire.

The EMEVD boss defeat and NPC position flags (6319, 1421, etc.) live in a different region. Boss kills remain detectable via inventory (boss souls).

#### Confirmed flag IDs (validated against 40-save QA corpus)

All fired at exactly the right steps — zero false positives, zero spurious clears:

| Flag | Event | Step |
|---|---|---|
| 1 | Entered Firelink Shrine | 6 |
| 48, 65, 193 | Tower on the Wall area reached | 12 |
| 112, 129, 176 | Cell Key / Greirat's cell area reached | 13 |
| 240, 257 | Talk to Emma (Small Lothric Banner given) | 15 |
| 288 | Curse-Rotted Greatwood defeated | 33 |
| 26995–27023, 27730 | Talk to Holy Knight Hodrick | 32 |
| 27470, 27761 | Greatwood fog gate / defeated cluster | 33 |
| 27793 | Pit of Hollows bonfire | 34 |
| 29042 | Talk to Leonhard (first interaction) | 35 |
| 29064 | Loretta's Bone given to Greirat | 36 |
| 34127 | Greirat sent to scavenge | 37 |
| 34079 | Cornyx at Firelink (later quest step) | 38 |
| 34085 | Dark Sigil drawn from Yoel | 40 |

From controlled saves (QA2 character — confirmed 0→1 on target event):

| Flag | Event |
|---|---|
| 28198 | Cornyx: first dialogue advancement |
| 28350 | Irina of Carim: first talk |
| 33244 | Irina of Carim: first talk (secondary) |

#### EMEVD sourced from DSMapStudio (m40, m30, m31, common)

Key findings for future flag work:
- **Boss defeat flags** (from `SetEventFlag` in EMEVD): 6319 Iudex, 6301 Vordt, 6302 Dancer, 6300 Consumed King, 6303 Greatwood, 6320 Champion Gundyr. Also 9xxx counterparts set simultaneously.
- **NPC quest state machine ranges** (from `SetNetworkconnectedEventFlag`): Greirat 1420–1439 (1421=recruited, 1438=dead), Yoel 1040–1059, Yuria 1060–1079, Cornyx 1100–1119 (1101=at Firelink), Irina 1460–1479 (1463=at Firelink, 1478=hostile), Siegward 1300–1319, Hawkwood 1020–1039, Orbeck 1180–1199, Sirris 1200–1219, Leonhard 1360–1379, Karla 1240–1259, Patches 1260–1279, Eygon 1340–1359 + 1480–1499.
- Stored in `data/_emevd_flags.json`.

#### BonfireWarpParam data (from DSMapStudio export)

- **`BONFIRE_NAMES` corrected** — previous area estimates were wrong. Correct formula: `WarpEventId // 10000 * 10 = area_code`. Confirmed: 3000 High Wall, 3100 Undead Settlement, 4000 Cemetery of Ash, 4100 Kiln, 5100 Ringed City. All 16 areas now mapped.
- **`data/_bonfire_flags.json`** — 81-entry `LocationEventId → bonfire name` dictionary (complete base game + DLC from BonfireWarpParam).

#### New files shipped this session

| File | Purpose |
|---|---|
| `parser/flags.py` | Flag reader: `read_flag(payload, name_offset, flag_id)`, `KNOWN_FLAGS` dict |
| `data/_bonfire_flags.json` | 81 LocationEventId → bonfire name (from BonfireWarpParam) |
| `data/_emevd_flags.json` | Boss defeat IDs + NPC state ranges from EMEVD |
| `scripts/find_flag_start.py` | Monotonic bit scanner that located FLAG_START_REL |
| `scripts/diff_controlled_saves.py` | Diffs controlled save pairs by flag_id (handles name_offset drift) |
| `scripts/parse_emevd_flags.py` | Extracts SetEventFlag calls from decompiled EMEVD |
| `scripts/validate_flags_qa.py` | Validates KNOWN_FLAGS against all 40 QA saves |
| `extract.py` | Now outputs `flags_set` per slot (human-readable flag labels) |

### Session 8 work — 2026-05-30 (advisor system + play simulator)

#### Play simulator (`play_simulator.py`)

Standalone script that replays a folder of numbered `.sl2` saves in sequence, copying each to `sim_workspace/DS30000.sl2`, parsing it, and printing what changed:

```
python play_simulator.py play_00          # 40-step QA playthrough
python play_simulator.py play_01          # 6 controlled save pairs
python play_simulator.py play_00 --interval 3   # 3s between steps
python play_simulator.py play_00 --no-tips      # diff only, no advisor
```

Key features:
- **Auto slot detection**: compares saves 1 and 2 to find which slot's playtime changed, then locks that slot for the whole run. Robust even when multiple characters exist in the save file.
- **State diff output**: level-ups, location changes, soul gains/losses, inventory in/out, named flag milestones — zero LLM tokens.
- **Advisor integration**: after each diff, matched tips are shown only when the tip set changes (no repeated identical messages). `[done]` printed when a tip exits scope.

Save folders live in `play_simulator_save_files/`:
- `play_00/` — 40-step QA playthrough (steps 01–40, slot 4)
- `play_01/` — 6 controlled save pairs (slot 5 / QA2)

#### Rule-based advisor (`advisor.py` + `data/tips.json`)

**Architecture: zero LLM tokens at runtime.**

Tips are stored in `data/tips.json` as structured rules. At runtime, `get_tips(state)` does pure Python condition matching — no LLM call.

**Tip schema:**
```json
{
  "id": "unique_id",
  "category": "item|npc|quest|lockout|boss|build",
  "title": "Short label",
  "tip": "Full tip text shown to player",
  "urgency": "warning|reminder|info",
  "triggers": {
    "bonfire_areas": ["Undead Settlement"],
    "has_items": ["Grave Key"],
    "missing_items": ["Pyromancy Flame"],
    "has_flags": [1, 28198],
    "missing_flags": [34079],
    "builds": ["dex", "str"],
    "min_level": null
  }
}
```

**Trigger logic** (ALL conditions must be true):
- `bonfire_areas` — current bonfire area must match one
- `has_items` — ALL items must be in inventory
- `missing_items` — NONE may be in inventory (tip is "not done yet")
- `has_flags` — ALL flag IDs must be set
- `missing_flags` — NONE may be set ("not done yet")
- `builds` — player build (detected from stats) must match one; `null` = any
- `min_level` — only show at/above this level

**Build detection** from current stats:
- DEX ≥ 20 and DEX > STR+4: `dex`
- STR ≥ 20 and STR > DEX+4: `str`
- INT ≥ 18: `int`
- FTH ≥ 18: `fth`
- INT ≥ 14 and FTH ≥ 14: `pyro`
- Otherwise: `balanced`

**Current tip database** (`data/tips.json`): 23 tips covering Cemetery of Ash → Undead Settlement, sourced from the FightinCowboy 100% walkthrough transcript. Key tips:

| ID | Area | Urgency | What it covers |
|---|---|---|---|
| `cemetery_crystal_lizard` | Cemetery of Ash | info | Titanite Scale from lizard |
| `firelink_sword_master_uchigatana` | Firelink | info | Uchigatana from Sword Master NPC (dex build) |
| `firelink_covetous_silver_serpent_ring` | Firelink | info | +10% soul ring in rafters |
| `firelink_tower_key` | Firelink (lvl 20+) | info | Tower Key → Firekeeper Soul + crow |
| `high_wall_claymore` | High Wall | info | Claymore from dragon bridge (str/dex) |
| `high_wall_free_greirat` | High Wall | reminder | Use Cell Key to free Greirat |
| `high_wall_emma_banner` | High Wall | reminder | Talk to Emma for progression item |
| `undead_settlement_hodrick_covenant` | Undead Settlement | **warning** | Don't kill Hodrick before Mound-makers |
| `undead_settlement_giant_archer` | Undead Settlement | **warning** | Talk to Giant first (Token of Friendship) |
| `undead_settlement_cornyx_cage` | Undead Settlement | info | Free Cornyx → pyromancy vendor |
| `undead_settlement_irina_sewer` | Undead Settlement | reminder | Use Grave Key → free Irina (miracles) |
| `firelink_give_loretta_to_greirat` | Firelink | reminder | Give Loretta's Bone before sending Greirat |
| `firelink_dark_sigil_warning` | Firelink | info | Usurpation path implications |
| ... | ... | ... | ... |

**Validated output** — tips fire at exactly the right steps with no false positives across all 40 QA saves and 6 controlled saves.

#### New files shipped this session

| File | Purpose |
|---|---|
| `play_simulator.py` | Active-play replay: copies each numbered save → parses → diffs → shows tips |
| `advisor.py` | `get_tips(SlotState) -> list[tip]`, `format_tips()` — zero tokens at runtime |
| `data/tips.json` | 23 hand-authored tips with trigger conditions |
| `sim_workspace/` | Working directory for the simulator's current save copy |

### Session 9 work — 2026-05-31 (FLAG_START_REL was wrong all along)

#### Core discovery: FLAG_START_REL = 0x11660 is the item registry, not flags

The `find_flag_start.py` script (written in Session 8 to investigate) has a comment in its header:

```
Previous findings:
  - 0x11660 relative: growing sorted index — NOT flags
```

`name_offset + 0x11660` is the **item registry** — a sorted list of item IDs the character has ever acquired. When we did monotonic analysis across the 40 QA saves and found "flags" at positional indices like 29064, we were observing items being added to this sorted list, not event flags being set. **All KNOWN_FLAGS entries derived from that analysis have wrong labels.**

This explains:
- Why `diff_controlled_saves.py` showed 2385 changes between quest-track saves 05 and 07 (buying Cell Key + giving bone + sigil draw all shifted the item registry)
- Why flag 29064 read 0 in gq-05 even though inventory confirmed the bone was given
- Why the "very high" flag IDs (1.5M+) appeared in diffs — those bits are actually far into the item registry

#### Actual flag bitfield location

The real EzState event flag bitfield starts at approximately:

```
name_offset + 0x403F4   (QA character, slot 4)
name_offset + 0x403F8   (Greirat character, slot 5)
```

**How confirmed**: clean same-name_offset diffs on QA corpus saves 35, 36, 37 (all name_offset = 0x10AA0):

| Event | abs position | byte change | bits set |
|-------|-------------|-------------|----------|
| loretta_bone_given (save 35→36) | 0x51CC5 | 0x00→0x0C | bits 2,3 |
| greirat_sent (save 36→37) | 0x51CC5 | 0x0C→0x0F | bit 0 added |
| greirat_sent secondary (36→37) | 0x51CCA | 0x00→0x04 | bit 2 |

With FLAG_START_ABS = 0x10AA0 + 0x403F4 = 0x50E94:
- byte offset in bitfield = 0x51CC5 - 0x50E94 = 0xE31 = **3633**
- Flag IDs in byte 3633: 29064 (bit 0), 29066 (bit 2), 29067 (bit 3)

Independently confirmed via greirat-quest controlled saves (slot 5, name_offset = 0x11E88): loretta_bone change at abs=0x530B1, which with FLAG_START_REL = 0x403F8 also gives byte 3633.

#### Corrected flag assignments

| Flag | Old label (WRONG) | Correct label |
|------|------------------|---------------|
| 29064 | Loretta's Bone given to Greirat | **greirat_sent_undead_settlement** (fires at save 37) |
| 29066, 29067 | (unlabeled) | **loretta_bone_given** (bits 2,3 of byte 3633, fire at save 36) |
| 34127 | Greirat sent to scavenge | **DISCARD** — derived from wrong FLAG_START_REL, meaningless |

All other KNOWN_FLAGS derived from the QA corpus monotonic analysis are similarly wrong labels and need re-derivation.

#### The 4-byte discrepancy

FLAG_START_REL = 0x403F4 for QA character (slot 4), 0x403F8 for Greirat character (slot 5) — a consistent 4-byte difference. The cause is unknown. **Next step to resolve**: load both characters from the same DS30000.sl2, compare their payloads at `name_offset + 0x403F0` to `+0x403FC` to find the structural 4-byte difference between slots.

#### Greirat-quest controlled save series

Location: `play_simulator_save_files/greirat-quest/`  
Character: slot 5, name = "Greirat"

| Save | name_offset | Notes |
|------|-------------|-------|
| 01 - Cell Key in hand | 0x10C0C | Before opening cell |
| 02 - Greirat freed, BTR received | 0x11E88 | BTR added; name_offset jumps +0x127C |
| 03 - DS30000.sl2 | 0x11E88 | Area reload, Greirat at Firelink |
| 04 - Loretta Bone in inventory | 0x11E88 | Bone in bag, not yet given |
| 05 - Loretta Bone given | 0x11E88 | Bone removed from inventory (confirmed) |

**Saves 02–05 all share name_offset 0x11E88** — clean for absolute diffs.

The candidate for `greirat_recruited` (flag 27291) found in s01→s02 diff was **disqualified**: it cleared between s03 and s04 (the Undead Settlement trip), so it is not a persistent quest flag.

Flag 1425 (EMEVD NPC state range 1420–1439, Greirat's block) was set during the s03→s04 transition (Undead Settlement trip). Its meaning is unknown but it's a candidate for an area-visit or Greirat state flag.

#### New script this session

`scripts/diff_greirat_quest.py` — diffs any two greirat-quest saves (slot 5, hardcoded), shows zone labels and checks for expected flags. Currently uses wrong FLAG_START_REL — **update after fixing FLAG_START_REL**.

#### Payload noise explanation

~300,000+ bytes change between consecutive saves even for single events. This is normal:
- The item registry (before name_offset) shifts when any inventory changes
- Region 0x78000–0xBFFFFF (last ~295 KB) changes nearly completely every save — likely a large re-serialized NPC state table or per-frame data
- Real flag signal is in isolated clusters away from these noisy regions

#### What needs fixing

1. **`parser/flags.py`**: change `FLAG_START_REL = 0x11660` to `0x403F4` (after resolving 4-byte issue). Replace all `KNOWN_FLAGS` with correctly labelled IDs.

2. **`decision_making_files/greirat_of_the_undead_settlement.json`** `flag_registry`:
   - `loretta_bone_given.id`: change from 29064 → **29066** (or add both 29066 and 29067)
   - `greirat_sent_undead_settlement.id`: change from 34127 → **29064**

3. **Re-run `scripts/find_flag_start.py`** on `play_simulator_save_files/play_00/` (script is hardcoded to `save_files/` — update the path) to re-derive all KNOWN_FLAGS under the new FLAG_START_REL.

### Recommended next steps (in order)

1. **Extract tips from FightinCowboy transcript via one LLM call** (`scripts/extract_tips_from_transcript.py`). Send the full transcript to Claude API once with a structured extraction prompt, get back JSON in `tips.json` schema. Adds ~50–100 more tips for Farron Keep, Cathedral, Irithyll, Catacombs, and beyond without any runtime token cost. Prompt template:
   ```
   Given this walkthrough transcript, extract every tip that can be triggered
   by a specific game state. Output JSON array matching this schema: [schema].
   Focus on: missable items, NPC quest steps, lockout warnings, build-specific
   weapons. Skip pure combat strategy unless it guards an item.
   ```

2. **Mine `data/*.csv` for build-aware item tips** (`scripts/build_tips_from_csv.py`). The 47 CSVs contain every weapon, armor, ring, and spell with location, stats, and scaling. A code-only script can auto-generate tips like:
   - Weapons with A/S scaling in DEX → dex build tip keyed to the area they're found in
   - Weapons with A/S scaling in STR → str build tips
   - Faith/Int catalyst locations → caster tips
   - Rings with generic value → universal tips
   Strategy: join weapon CSVs with wiki location data to produce `triggers.bonfire_areas` + `triggers.builds` automatically.

3. **Expand the flag dictionary** — add more controlled save pairs for Greirat at cell, Siegward (windmill, well, Irithyll), Yoel free-level draws, Anri/Horace. Each pair: one save just before, one just after, run `scripts/diff_controlled_saves.py`. Adds ~5–10 flags per pair, enabling more precise tip triggers.

4. **Locate EMEVD boss flag store** — to read 6319 (Iudex), 6301 (Vordt), etc. directly. Required for boss-kill tips that don't rely on boss souls in inventory (e.g. "You just beat Vordt — grab the Basin of Vows from Emma now").

5. **Small parser fields** — item-registry walker, hollowing count, NG cycle.

### What's pending (in priority order)

0. **Extract tips from transcript** (one LLM call) — see step 1 above.
1. **Mine CSVs for build-aware tips** (code only) — see step 2 above.
2. **Expand EzState flag dictionary** — controlled saves for Greirat, Siegward, Yoel, Anri.
3. **Locate EMEVD boss flag store** — to read 6319, 6301, 6303 etc. from save.
4. **Full item-registry walker** — 60-byte records in `0x60+` region before `name_offset`.
5. **Hollowing count** — small u8/u32 near stat block.
6. **NG cycle** — small u8. Dark Tarnished is NG+5; all others NG+0.

### Controlled-saves workflow

Controlled save pairs live under `play_simulator_save_files/` (e.g. `play_01/`), numbered:

```
play_simulator_save_files/play_01/
  01_-_Before_Talk_to_Greirat.sl2
  02_-_After_Talk_to_Greirat.sl2
  ...
```

Then run:
```
python scripts/diff_controlled_saves.py before.sl2 after.sl2 --slot N
```

This diffs each consecutive pair by flag_id (handles name_offset drift between saves), prints all newly set flag IDs, and cross-references against `data/_event_flags.json`. Add discovered flag IDs to `parser/flags.py` KNOWN_FLAGS and `data/tips.json` triggers.

### Gotchas worth remembering

- **Python 3.10** on Windows (C:\Program Files\Python310\python.exe — no venv in repo, install deps globally with pip).
- **Save file at `DS30000.sl2`** is the Wanderer mule (downloaded from internet, 10 slots Alpha…Kappa) — used as the canonical test fixture for `tests/test_slots.py`. **Not** to be confused with an actual game save.
- **QA character is slot 4** ("QA"), QA2 character is slot 5 ("QA2") — controlled saves used QA2.
- **Item ID JSONs in `data/_*.json`** are from alfizari's GPL-3 DS3 editor. They're cached locally; license-compatible for personal use but re-evaluate before any redistribution.
- **AES key**: `fd 46 4d 69 5e 69 a3 9a 10 e3 19 a7 ac e8 b7 fa` — public, sourced from `jtesta/souls_givifier`.
- **Reasoner output is VERY verbose for save-editor mule saves** (every soul triggers Ludleth advice). That's correct rule behaviour, but for a chat-UX layer we'll want per-save rate-limits. Not urgent.

---

## Game choice: Dark Souls 3

Decision: build for **DS3** first.

Rationale (vs DS1, DS2, Elden Ring):

- **DS3 has the highest value density per warning.** Quest lockouts in DS3 are notoriously fragile and well-documented — Yoel/Yuria, Anri/Horace, Sirris, Siegward, Greirat, Orbeck, Cornyx/Karla — and players regularly break them by accident.
- **4 endings with clean flag dependencies** make ending steering tractable.
- **Best community modding tooling of any Souls game** (Smithbox, DSMapStudio, Yapped Rollo).
- **This repo already contains** 1,289 wiki markdowns and a full CSV item catalog — equal or better than what we have for DS1.
- DS2 was rejected: smaller modding scene, fewer iconic lockouts, mechanics (Soul Memory, Bonfire Ascetics, Fragrant Branches) don't map cleanly to "do this next" guidance.
- Elden Ring was rejected for v1: highest total addressable value but open world makes "what's next?" a ranking problem with no canonical answer; save format is also a moving target across patches.

DS1 remains useful as a prototype platform — `parse_save.py` already exists and works. Architecture proven on DS1 ports to DS3.

---

## What the save file actually gives us

Decrypted `.sl2` (AES-CBC, key public) exposes a **snapshot of state**, never an event stream:

| Primitive | Notes |
|---|---|
| Inventory | Items + counts per slot type (weapon, armor, ring, good) |
| Stats | Level, attribute spread, souls, hollowing, deaths |
| Event flags | Large bitfield. Each bit = one game-state boolean. Hundreds of thousands of bits; meaningful subset is small. |
| Equipped slots | Weapons, rings, attuned spells |
| Last bonfire rested at | Proxy for "where the player is" |
| Covenant + rank | |
| NG cycle, playtime | |

We recover history via two mechanisms:

- **Diffing snapshots** (between bonfire rests / quits) gives derived events: `bonfire_lit`, `npc_died`, `item_gained`, `level_up`.
- **Current-state predicates** drive most rules: "you have X, missing Y, and flag Z is set."

### Things we genuinely cannot detect

- Real-time advice during combat (save isn't written mid-fight).
- Dialogue lines heard without an associated flag (rare in DS3 — most major lines flip flags).
- Player intent (we see "INT 14, no catalyst" — we don't know if they meant to be a sorcerer).
- Exact ordering of two events that happened between bonfires.
- Things seen vs missed (no fog-of-war).

---

## Public resources catalogued

| Resource | What it provides | Status |
|---|---|---|
| [soulsmodding.com DS3 event flag list](https://soulsmodding.com/doku.php?id=ds3-refmat:event-flag-list) | ~200+ semantically labeled flag IDs (bosses, NPCs, covenants, story progression). Last updated March 2025. | Primary flag dictionary — scrape into JSON. |
| [mamalakic/darksouls3-auto-tracker](https://github.com/mamalakic/darksouls3-auto-tracker) | Python+Flask. Decrypts DS3 `.sl2`, parses inventory, diffs against achievement lists. | Reference code only (2 commits, unmaintained). Inventory-only — no flag reading. |
| [alfizari/Dark-Souls-3-Save-Editor-PS4-PC](https://github.com/alfizari/Dark-Souls-3-Save-Editor-PS4-PC) | Full DS3 save editor; exposes slot offsets for stats, equipment, inventory. | Source for offset tables. Same author as our DS1 reference. |
| [jtesta/souls_givifier](https://github.com/jtesta/souls_givifier) | GPL-3 multi-game (DSR/DS2/DS3/ER) save modifier. Python + JS. | Confirms AES-based encryption family; useful for cross-checking. |
| [Meowmaritus boss EventEntityIDs gist](https://gist.github.com/Meowmaritus/8f16d27988f907ddedf882405642b096) | ~40 DS3 bosses + variants (DLC included) keyed by entity ID. | Cross-reference for boss-kill rules. |
| [Smithbox](https://github.com/vawser/Smithbox) / [DSMapStudio](https://github.com/soulsmods/DSMapStudio) | Full modding tools. Expose param tables, EMEVD scripts. | Ground truth if a flag ID isn't in the wiki list. |
| [EMEVD format docs](http://soulsmodding.wikidot.com/format:emevd) | The event-script format that generates flags. | Reference only — we consume flags, don't parse EMEVD. |
| [JKAnderson/EventPocket](https://github.com/JKAnderson/EventPocket) | Realtime flag viewer for DS1/DSR. | Pattern reference for "watch flags live". |

---

## What we already have locally

- `data/` — 47 CSV files covering every item category (weapons, armor, rings, sorceries/miracles/pyromancies, ashes, gestures, sacred chimes, staves, boss souls, boss soul weapons, multiplayer items, upgrade materials, achievements).
- `data/wiki/` — 1,289 wiki markdown files.
- `all_wikipedia_content.md` — 13.9 MB consolidated wiki.
- `scraper.py`, `wiki_md_scraper.py` — scraping infrastructure.

What we **don't** have for DS3 yet:

- `parse_save.py` equivalent.
- `_ids_*.json` item ID maps.
- A sample `.sl2` to test against.

---

## What needs to be built

In rough dependency order:

1. **DS3 save parser** (Python, modeled on the DS1 `parse_save.py`). Output: typed state object `{inventory, flags, stats, last_bonfire, covenants, equipment}`. Reuse decryption + container parsing from `mamalakic` / `alfizari`. New work: locate the event-flag bitfield region in the slot data and write a reader. Validate by toggling known flags in-game and re-reading.
2. **Item ID maps** for DS3 (fetch from alfizari's resources or build from CSVs).
3. **Flag dictionary scraper**: pull soulsmodding's DS3 event flag list into structured JSON. Supplement with bonfire flags if missing (derive from EMEVD via Smithbox if so).
4. **Watcher daemon**: file mtime poller; emits `(prev_state, new_state)` pairs.
5. **Event synthesizer**: diffs two states → list of events.
6. **Rule engine**: declarative `WHEN (predicate) THEN (advice)` rules. Priority + dedup.
7. **Rule authoring** — the long tail; see catalog below.
8. **LLM layer**: ranks + rephrases fired rules into friendly text. Not used for deciding what fires.
9. **Transport / server**: receives state summaries from client, runs rules, returns suggestions. State summary travels — not the raw `.sl2`.

---

## Suggestion catalog (target content)

Rule categories with rough v1 sizing:

| Category | Description | Rule count | Effort |
|---|---|---|---|
| A | Hard lockout warnings (irreversible) | 25-30 | high — per-rule research |
| B | Soft lockouts / "you didn't know there was a quest here" | 20-30 | medium |
| C | Point-of-no-return checklists (Kiln entry, DLC entry, NG+ transition) | 4-6 (each fires many sub-checks) | high |
| D | Ending steering | 6-8 | medium |
| E | Build viability (catalysts/chimes for stats, soft caps, weapon upgrade paths) | 15-20 | low (templated) |
| F | Covenant progression (offering counts, where to farm) | 10-15 | low |
| G | Achievement / completion tracking (extends existing DS1 approach) | auto-derived from CSVs | low |
| H | Event-triggered tips (bonfire lit / boss killed / item gained) | 40-60 | low-medium |

**Total target: ~120-180 rules.** Heavy effort concentrated in A + C + D (~50 rules) — that's the content moat.

### Example rules per category

**A — Hard lockouts** (representative; not exhaustive)
- Yoel: warn before Catacombs of Carthus bonfire if sigils < 5 and Usurpation desired; report Yuria lockout if Yoel dies with < 5 sigils.
- Greirat (Undead Settlement pillage): require Loretta's Bone in inventory.
- Greirat (Irithyll pillage): require Patches at Firelink.
- Sirris: warn before any of her 3 summon-sign fights if sign not used.
- Siegward (Profaned Capital cell): require Old Cell Key before Yhorm.
- Cornyx / Karla tome conflict: any pyromancy tome given to Karla locks Cornyx out of those spells, and vice versa for dark tomes / Irina.
- Anri/Horace: warn before Catacombs hidden floor if Anri questline not advanced.

**B — Soft lockouts**
- Cathedral of the Deep painting (Ariandel entry) not examined.
- Eygon hostility risk when buying dark miracles from Irina.
- Velka statue available — relevant if dark sigils present.
- Sirris summon at Curse-Rotted Greatwood missed (quest desyncs).
- Small Doll picked up → Watchdogs covenant entry now reachable.

**C — Point-of-no-return checklists**
- Kiln of the First Flame: roll up Siegward / Anri / Sirris / Greirat / Orbeck / Cornyx / Karla / Yuria / Eyes of a Fire Keeper / DLC entries.
- Ariandel painting entry: warn about pickups inside.
- Soul of Cinder defeat → NG+ imminent: list items that don't carry.

**D — Ending steering**
- Current ending track + what's needed to switch.
- Eyes of a Fire Keeper: must give before SoC.
- Yuria + 5 sigils + Anri stab = Usurpation; status check.

**E — Build viability** (templated)
- "INT 14+ and no catalyst": list 3 nearest options based on last bonfire.
- "FAITH 20+ and no chime": same.
- Weapon upgrade level vs SL → recommend +N before more stat points.
- Boss souls in inventory: list Ludleth trades available.

**F — Covenant management**
- For each covenant: rank, offerings owned, best farm location, NPC status (alive/reachable).

**G — Achievement tracking** (extends existing DS1 approach)
- Master of Sorceries/Miracles/Pyromancies/Rings/Weapons — diff inventory vs CSVs.
- For each missing item: who sells it / where it's found / whether that NPC is still alive this cycle.

**H — Event-triggered tips**
- Bonfire lit: nearby missables, NPC introductions, hidden walls.
- Boss killed: trades available, areas now reachable, related quest steps.
- Major item gained: what it unlocks.

---

## v1 scope recommendation

Ship narrow but impressive. Goal: player feels "this noticed something I would have missed" within first 5 hours.

- All of category G (mechanical, near-free since DS1 logic ports).
- Top 15 rules from A (highest-pain lockouts).
- The Kiln checklist from C (single marquee feature).
- ~20 event-triggered tips from H (bonfire-rest nudges).

That's ~50 user-visible rules + automatic achievement tracking. Tractable in 2-3 weekends after the parser+flag-reader are working.

---

## Architectural decisions made

### Parsing & transport
- **v0 sends the raw `.sl2` to the server**, which decrypts and parses it. The earlier draft argued for client-side parsing on trust grounds (uploading saves clones the character) — that concern applies to a multi-tenant SaaS, not to a personal home server. A dumb client is much faster to iterate. **Revisit before exposing this beyond a single user**: at that point switch to client-side parse + state-summary upload.
- **Watcher polls file mtime every ~2s.** Native FS events (`watchdog` / `ReadDirectoryChangesW`) are an upgrade path, not a starting point.
- **The save is written at discrete moments only**: bonfire rest, quit-to-menu, death, certain story events / cutscenes. Nothing to miss by polling.
- **Steam Cloud can rewrite the file** when the game isn't running. Dedupe on **parsed-state diff**, not mtime alone — a touch with no state change produces no events.
- **Read shared, wait for size to stabilise** (two consecutive polls ~200ms apart with the same size) before parsing, to avoid torn reads while DS3 is mid-write.

### Rule engine + LLM
- **Rule engine is deterministic.** The LLM is for *phrasing* and *ranking*, not for deciding what triggers. Hallucinated quest advice is the worst possible failure mode.
- **Most save events produce zero messages.** Cap at 2-3 messages per save event even if more rules fire. A chat feed becomes noise fast if every bonfire rest generates five lines.

### Storage
- **SQLite on the server.** Single file, zero ops, plenty fast for one user.
- **Prior parsed state lives on the server** (the side that diffs).
- **Chat history is persisted**; an **FTS5 virtual table** gives free full-text search alongside structured filters (category, date, character, rule_id).

### Client / UX
- **Windows watcher**: plain Python script run from a venv. PyInstaller + tray icon deferred until a non-dev user needs it.
- **Surface**: mobile-first React PWA (Vite + Tailwind + shadcn — same stack as `prometheux-rag-78`), running on iPad / phone as a second screen while playing.
- **Push channel**: Server-Sent Events. Traffic is asymmetric (server push + occasional client request) — WebSockets aren't justified.
- **Network**: LAN-only for v0. No Tailscale / Cloudflare Tunnel yet. Plain HTTP on the LAN; HTTPS becomes necessary if/when we install as a real iOS PWA or expose beyond the house.
- **Character selection is app-level.** First run: parser lists all populated slots (name + level + last-played); user picks one and that choice is sticky. Feed and prior-state are per-character.

---

## Parser progress

Implemented and tested against the canonical 10-slot Wanderer save at `DS30000.sl2`:

| Field | Source | Offset / location |
|---|---|---|
| Character name | slot payload | `0x019FEC`, UTF-16-LE, up to 16 chars |
| Class | slot payload | `0x01A012`, u16 LE — Knight=0, Mercenary=1, Warrior=2, Herald=3, Thief=4, Assassin=5, Sorcerer=6, Pyromancer=7, Cleric=8, Deprived=9 |
| Sex | slot payload | `0x01A00E`, u16 LE — `1`=Male observed; `0`=Female assumed (not yet verified against a Female save) |
| Playtime | slot payload | offset `8`, u32 LE, **milliseconds** |
| Level | slot payload | `0x019FD4`, u32 LE |
| Souls | slot payload | `0x019FD8`, u32 LE |
| 9 attributes (VIG, ATT, END, STR, DEX, INT, FTH, LCK, then VIT) | slot payload | `0x019FA8` onward, each u32 LE; VIT split off at `+0x28` |
| Inventory grid | slot payload | `0x01A3D0`, 16-byte records, item_id at +4 (high byte = category), count at +8; internal sentinel gaps up to ~26, real end at much longer run |
| Item ID → name map | local `data/_weapons.json`, `_armor.json`, `_ring.json`, `_goods_magic.json` | fetched from alfizari DS3 save editor |
| User-data (per-slot occupancy + load-screen summary) | BND4 entry 10 | `parser/userdata.py` |
| Last bonfire rested at | BND4 entry 10, per-slot record | offset `+50`, u16 LE. Empirically confirmed: 3000, 3100, 4000, 4005, 4100, 5100. Full dict in `BONFIRE_NAMES`. |
| Currently-equipped weapons | slot payload | `name_offset+492` (left hand), `name_offset+496` (right hand), u32 LE, direct weapon-map lookup |
| Currently-equipped armor | slot payload | `name_offset+540/544/548/552` (head/chest/hands/legs), u32 LE, stored with high byte `0x01`; lookup via lower-3-byte key into armor map |
| Currently-equipped rings | slot payload | `name_offset+556/560/564/568` (ring slots 1–4), u32 LE, direct ring-map lookup |
| AES key | hardcoded | `fd 46 4d 69 5e 69 a3 9a 10 e3 19 a7 ac e8 b7 fa` |

Tests: 9 passing, 13 skipped (corpus saves not on disk). Run `python -m parser.cli <path-to-sl2>` for a per-slot summary.

## Still to map (post-v0 parser work)

### Event-flag bitfield
The big one. Required for every quest/lockout/ending rule. Not documented in the references found so far. Path forward: rest at one bonfire, save; rest at another bonfire, save; diff the two slot payloads to find which bits changed. Repeat with NPC interactions to find quest flags. Smithbox EMEVD scripts give the flag-ID-to-event mapping once we have the bitfield location.

### Last bonfire (which bonfire you'll spawn at)
**Resolved 2026-05-28.** Lives in userdata (BND4 entry 10), per-slot record offset **+50, u16 LE**. `BONFIRE_NAMES` in `parser/userdata.py` now covers all base-game and DLC areas. Empirically confirmed IDs: 3000, 3100, 4000, 4005, 4100, 5100. Remaining entries estimated from area-numbering pattern — verify from controlled saves as needed.

### Currently-equipped slots
**Resolved (2026-05-28, session 3).** Equipment slots live at fixed offsets from `name_offset` in the slot payload (see "Parser progress" table above). `parser/equipment.py` reads all 10 slots (2 weapon + 4 armor + 4 ring). Validated against all 20 QA saves — fresh Knight correctly shows Long Sword + Knight Shield + full armor set from slot 1.

The region from `0x60` to `~name_offset` is still the **item registry** (60-byte records, handle at +0, item_id at +4, durability at +8). It covers owned-but-unequipped upgradeable items — not yet iterated. See pending item #1.

### Other deferred slot fields
Deaths, hollowing — likely small u8/u32 fields near the stat block. All zeros for the mule save so can't anchor without a save with progress.

---

## Open questions (still to verify)

- License/attribution: confirm the soulsmodding flag list and alfizari ID JSONs can be redistributed if we ever ship beyond local use.

---

## Deferred to post-v0

### Interactive agent ("ask the companion") — planned v1
v0 ships **proactive only**: the server notices, the server speaks. The companion is a one-way feed. We deliberately defer the two-way conversation to land reasoning over states first.

When we add it:

- Add `POST /ask` alongside the SSE feed. Traffic stays asymmetric — still no WebSocket needed.
- Agent answers are grounded in three tools:
  - `query_state(...)` — current parsed save (flags, inventory, NPC statuses, last bonfire)
  - `evaluate_rule_hypothetical(...)` — "would rule X fire if I did Y?", using the existing predicate library
  - `search_wiki(...)` — RAG over the 1,289 wiki markdowns in `data/wiki/`
- Build a **wiki RAG index**: `sqlite-vec` (or Anthropic embeddings) over the wiki corpus. Static content, cheap to maintain, no incremental indexing needed.
- This is the same Prometheux-shaped agent pattern as `jarvispy`'s `VadalogAgent` — tool-using LLM, RAG, deterministic backends. Reuse mental models and code patterns where it makes sense.

Example interactions to design toward:

- "Should I kill Abyss Watchers now?" → agent calls `evaluate_rule_hypothetical(boss=AbyssWatchers)` to enumerate triggered lockouts, summarises.
- "Tell me about Yuria's questline." → wiki RAG.
- "Where can I find a catalyst from here?" → wiki RAG + `query_state(last_bonfire=...)`.

### Other deferred items
- PyInstaller package + system tray for non-dev users on Windows.
- iOS PWA install + web push notifications (iOS 16.4+ supports push for installed PWAs).
- Tailscale or Cloudflare Tunnel for off-LAN access.
- `watchdog`-based native FS events on Windows — only if mtime polling shows up as a problem.
- Multi-user / multi-tenant: at that point, revisit "raw `.sl2` upload" and switch to client-side parse + state-summary upload.

---

## Live Memory Reading (Alternative Approach)

Not yet implemented — requires DS3 running on the same machine. Deferred until tested on the gaming PC.

### Motivation

The save file is only written at discrete moments (bonfire rest, death, quit to menu). NPC dialogue flags flip in RAM immediately when the dialogue node fires but are **not flushed to disk until the player quits**. If a player talks to Greirat, sends him on a mission, and dies — the flag never appears in the save file for that session. Memory reading solves this.

### Comparison with save file approach

| Dimension | Save file | Memory reading |
|---|---|---|
| **Trigger** | DS3 writes the file (bonfire, death, quit) | Your poll interval (e.g. 200–500ms) |
| **NPC dialogue flags** | Only after quit | Live — fires within 500ms |
| **Quest flag transitions** | Only after quit | Real-time |
| **Player position / zone** | Not available | Available |
| **Enemy HP / aggro** | Not available | Available |
| **Inventory, stats, equipment** | Full snapshot | Same, live |
| **Latency** | 1–3s (poll + settle) | ~200–500ms |
| **Complexity** | Already built | Needs pymem + offset table |
| **EAC risk** | None | Incompatible online — safe offline only |

Memory reading is a **strict superset** of the save file. The save file approach remains sufficient for post-bonfire summaries; memory reading unlocks real-time NPC tracking.

### Option A: External process memory reading (recommended starting point)

No mod, no DLL injection. Read the DS3 process RAM from Python via `pymem`.

```python
import pymem
pm = pymem.Pymem("DarkSoulsIII.exe")
# read a u32 at a known base + offset chain
value = pymem.process.read_int(pm.process_handle, base + offset)
```

- The DS3 community has documented most critical offsets via Cheat Engine tables (event flags, player stats, position, NPC quest states).
- Poll on a timer; compare against previous read to emit events.
- Integrates cleanly alongside the existing save file watcher — run both in parallel.
- **EAC**: never run while connected to multiplayer. Offline/single-player: safe.

**Key library**: `pymem` (pip). Alternative: `pyMeow` (wraps Frida).

### Option B: DLL injection mod

Inject a DLL into DS3 via **Mod Engine 2** (the standard DS3 mod loader). Hook game functions to get push-style callbacks on events instead of polling.

- More accurate event timing; zero polling overhead.
- Significantly more complex: need to reverse-engineer DS3 function signatures.
- Mod Engine 2 handles DLL loading without modifying game files.
- Still EAC-incompatible online.

**Use only if** Option A's polling latency proves insufficient (unlikely for this use case).

### What memory reading adds to the pipeline

The save file diff already covers ~26 of 40 first-playthrough milestones (boss kills via boss souls, key-item pickups, level-ups, bonfire transitions). The ~14 "silent" steps — pure NPC-dialogue milestones — are exactly what memory reading unlocks:

| Currently silent step | What memory reading would expose |
|---|---|
| Talk to Greirat (pre-rescue) | Dialogue flag fires immediately |
| Send Greirat to scavenge | Quest state flag 1421 (recruited) → 1422+ |
| Talk to Irina in sewer | Dialogue flag → can trigger tip before quit |
| Yoel free-level draws mid-session | Hollowing + Dark Sigil flag in real time |
| NPC killed without saving | Death flag visible before next bonfire |

### Resources for offset research

- **DS3 Cheat Engine tables** (community-maintained) — document player stats, event flags, NPC state machine ranges, position, enemy HP. Search "DS3 CE table" on The Grand Archives wiki / Nexus.
- **JKAnderson/EventPocket** (DS1/DSR) — pattern reference for live flag watching (see "Public resources" table above).
- **SpeedSouls / DS3 practice tools** — open source, read DS3 memory directly; good code reference.
- **EMEVD flag ranges** already in `data/_emevd_flags.json` — NPC state machine IDs (Greirat 1420–1439, Irina 1460–1479, etc.) are the primary targets.

### Integration plan (when ready to implement)

1. Install `pymem` in the venv.
2. Build a `memory_reader.py` module: find DS3 base address, walk pointer chains to the event-flag region and NPC state arrays.
3. Poll every 200–500ms in a background thread; emit events when a flag transitions 0→1.
4. Feed events into the same `advisor.get_tips()` pipeline the watcher uses.
5. Optionally suppress the save-file watcher's flag diff when memory reader is active (to avoid double-reporting).

---

## Reference: existing DS1 prototype

`/Users/mozartdiniz/Dev/dark-souls/DS/parse_save.py` — working DS1 inventory extractor + achievement diff report. Demonstrates the parser → ID map → category diff → report flow. Architecture transfers; offsets and ID maps do not.
