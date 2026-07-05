# Event Flag Research

**STATUS: SOLVED (2026-06-11, session 10).** Event flags are now read structurally
and semantically from the save. This file documents the working model. For the
investigation history (sessions 4–9 false starts), see [session_log.md](session_log.md).

---

## The working model

### 1. Locating the flag section — structural walk, not scanning

The slot payload is a *sequential serialization* of game structures. Walking it
field-by-field (the same walk used by alfizari's save editor `parse_save()`)
lands on the event-flag section deterministically:

```
0x6C                 gaitem registry: 6144 entries, 8 bytes each,
                     +52 extra bytes for each weapon/armor instance  (VARIABLE SIZE)
 -> end + 0x13F      "magic" block
 -> + 0x1DD          inventory (fixed 0x8808)
 -> + 0x11C          counted table 1 (u32 count, 8 bytes/entry)      (VARIABLE SIZE)
 -> + 0x18C + 4      storage box (fixed 0x8800)
 -> + 0xC + 0xA4     gestures, then counted table 2 (u32, 4 b/entry) (VARIABLE SIZE)
 -> + 0x92           new_game_plus field
 -> + 0xBCC          event_flag_start  — FIXED SIZE section, 0x33E5E bytes
```

Implemented in `parser/flags.py: find_event_flag_start()`. The three variable-
size structures are why every fixed-offset / name_offset-relative approach
failed: the section slides by the *sum* of their size changes (observed +0x127C
when the gaitem registry grew, +0x1C when the acquired-item index grew with no
name_offset change).

NOTE: payloads from `crypto.decrypt_entry()` have the 4-byte length prefix
stripped; alfizari's published offsets are 4 bytes higher (their gaitem start
is 0x70).

### 2. The blob — byte-for-byte the in-game world-flag memory

At `event_flag_start + 0x5D` begins an exact copy of the in-memory world-flag
blob that the TGA cheat table reads at `[[SprjEventFlagMan]+0]`. Proof: every
hardcoded offset in alfizari's boss/bonfire tables equals the corresponding TGA
cheat-table memory offset + 0x6F, and all 156 extracted CT (offset, bit) entries
decode consistently.

### 3. Semantic flag IDs — the codec

Flag IDs are the same ones used by EMEVD scripts, the soulsmodding wiki list,
and cheat tables:

```
8-digit:  T AABB CCC(C)        e.g. 13000800 = T1, map m30_00, local 800
commons:  id < 30720           e.g. 1225 (NPC state machines), 6301, 9210
```

- `T` — system digit: **1** = event flags, **6** = object flags (doors,
  shortcuts), **7** = talk flags (NPC dialogue milestones)
- `AABB` — map code (3000 = m30_00 High Wall … 5110 = m51_10 Filianore's Rest)
- `local` — flag index within the map block (0–10239; can be 3 or 4 digits)

Within the blob:

```
byte = REGION_ORIGIN[T] + MAP_SLOT[AABB] * 0x500
       + (local // 32) * 4 + 3 - ((local % 32) // 8)
bit  = 7 - local % 8
```

The `+3-(...)` term: flags are stored as u32 **little-endian** words with
local 0 at bit 31 (MSB-first). Commons occupy blob `[0x000, 0xF00)` with the
same u32 scheme (ids 0–30719).

Region origins (empirically verified):

| T | origin  | verified via |
|---|---------|--------------|
| 1 | 0x00F00 | TGA CT world-flag entries (bonfires, boss kills) |
| 6 | 0x1FE00 | TGA CT door/shortcut entries; Greirat cell door 63000156 |
| 7 | 0x2A300 | talk flags 74000600/74000300/74000850 across 3 characters |

Map slots (`(CT_base - 0xF00) / 0x500`): m30_00=0, m30_01=1, m31_00=2,
m32_00=4, m33_00=6, m34_01=8, m35_00=9, m37_00=12, m38_00=13, m39_00=14,
m40_00=15, m41_00=16, m45_00=17, m50_00=20, m51_00=21, m51_10=22.
(Gaps are unidentified/cut maps; blocks between region origins that don't map
to a known slot surface as `?block` entries in diff tooling.)

Implemented in `parser/flags.py: flag_offset()` / `decode_offset()`.

---

## Validated flag IDs (KNOWN_FLAGS)

Validation: `scripts/validate_flags_qa.py` — **0 failures across 41 flags ×
40 saves** (play_00 corpus), plus cross-checks on quest-track (slot 4,
modded character) and greirat-quest (slot 5) corpora. Same semantic IDs decode
from all three characters.

### Boss defeats (local 800 pattern; 801 = encountered)

13000800 Vordt · 13100800 Greatwood · 13300800 Abyss Watchers · 13300850
Crystal Sage · 13500800 Deacons · 13800800 Wolnir · 13800830 Old Demon King ·
13700800 Aldrich · 13700850 Pontiff · 13900800 Yhorm · 13000890 Dancer ·
13000830 Oceiros · 13010800 Dragonslayer Armour · 13410830 Twin Princes ·
13200850 Nameless King · 14000800 Iudex · 14000830 Champion Gundyr · 14100800
Soul of Cinder · 14500800 Friede · 14500860 Gravetender · 15000800 Demon
Prince · 15100800 Halflight · 15100850 Midir · 15110800 Gael

(Several mid/late-game IDs derive from CT offsets and still want an in-corpus
confirmation kill — only Iudex/Vordt/Greatwood have been observed flipping.)

### Bonfire-lit flags

The 81 LocationEventIds in `data/_bonfire_flags.json` ARE these flags
(13000003 = High Wall bonfire, etc.) and are directly readable now.

### NPC quest milestones (all observed flipping at the right step)

| Flag | Event | Observed |
|------|-------|----------|
| 63000156 | Greirat's cell opened | play_00 s14, gq s02, qt s03 |
| 1224 → 1225 → 1226 | Greirat commons state: in cell → recruited → away scavenging | all 3 corpora |
| 74000300/301 | Loretta's Bone given | play_00 s36, gq s05, qt s07 |
| 74000302/303 | Greirat sent to Undead Settlement | play_00 s37, qt s11 |
| 73100150/151/152 | Talked to Yoel (dying pilgrims) | play_00 s19, qt s04 |
| 74000400 | Yoel: Dark Sigil drawn (free level) | play_00 s40, qt s07 |
| 1084 → 1085 → 1086 | Yoel commons state: initial → at Firelink → dead | qt s04, s12 |
| 1064 → 1065 | Yuria appeared at Firelink | qt s12 |
| 74000600 | Talked to Yuria (label matches TGA CT exactly) | qt s12 |
| 73100100/101/102 | Talked to Irina (sewer cell) | play_00 s31, qt s08 |
| 1304→1305, 1324→1325 | Irina commons state advance (freed/accepted) | qt s08 |
| 74000350 | Talked to Irina at Firelink | play_00 s39 |
| 73100300/301/302 | Talked to Eygon (at Irina's cell) | play_00 s28, qt s08 |
| 73100363–367 | Siegward talk after Fire Demon | play_00 s27 |
| 73100400/401 | Talked to Hodrick (Pit of Hollows) | play_00 s32 |
| 74000850 | Talked to Leonhard (label matches TGA CT exactly) | play_00 s35 |
| 74000450/451 | Talked to Cornyx at Firelink | play_00 s38 |

### Volatile flags — do NOT use as triggers

These toggle back and forth depending on where/when the save was written
(event-script runtime state, NPC schedules): map locals 5000–6999 in the
type-1 blocks (e.g. 14005xxx), 74000103–108, 74000810–813, commons 4175/4180.
The advisor only reacts to curated KNOWN_FLAGS, so these are harmless noise in
raw diffs.

---

## Workflow: labelling new flags

1. Save before the event, save after (any character, any slot).
2. `python scripts/diff_greirat_quest.py before.sl2 after.sl2 --slot N`
   (or run `diff_controlled_saves.py before.sl2 after.sl2` on pairs kept
   under `play_simulator_save_files/`).
3. Output is semantic IDs. Cross-reference `data/_event_flags.json` (wiki),
   `data/_emevd_flags.json`, the TGA cheat table NPC list, or just trust the
   ID structure (7AABB = talk flag in map AABB).
4. Add to `KNOWN_FLAGS` in `parser/flags.py` + an expectation in
   `scripts/validate_flags_qa.py`.

---

## Reference sources

- **alfizari/Dark-Souls-3-Save-Editor-PS4-PC** (`src/main_ds3.py parse_save()`)
  — the structural payload walk; boss/bonfire byte offsets.
- **The-Grand-Archives/Dark-Souls-III-CT-TGA** (`DS3_The-Grand-Archives.CT`)
  — 156 in-memory world-flag (offset, bit) pairs; NPC commons flag list
  (1201 Greirat at shrine etc.); talk-flag labels (74000600 Yuria, 74000850
  Leonhard) that independently confirmed our decodes.
- `scripts/verify_alfizari_walk.py` — the verification harness from the
  session that cracked this.
- `scripts/decode_flag_diffs.py` — corpus-wide semantic diff dumps.

## Historical note

Sessions 4–9 tried: absolute offsets, name_offset-relative offsets
(`FLAG_START_REL` 0x11660 and 0x403F4/0x403F8), a content-scanned
"(group_key, block_index) directory" (`find_bit_blocks_start`) — all wrong or
non-portable. 0x11660 was the acquired-item index; the 0x403F4 bitfield was the
right *region* but with raw positional indices instead of semantic IDs, broken
by the variable-size structures in front of it. The EzState/EMEVD "three flag
stores" theory was also wrong: there is ONE world-flag blob holding event,
object, talk, and commons flags in typed regions.
