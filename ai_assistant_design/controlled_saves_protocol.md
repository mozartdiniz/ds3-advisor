# Controlled saves — Undead Settlement run

Purpose: a sequence of saves with **one (or a small known number of) flag flips between adjacent steps**, so that diffing the decompressed entry 11 between consecutive saves isolates which bytes/bits encode a specific event flag's set/unset state.

Once that encoding is cracked, the same diff series doubles as a rule-coverage validation: every step's expected advice can be cross-checked against what the reasoner actually produces.

---

## How to drop a save

For each checkpoint below, create a folder and copy your live `.sl2`:

```
play_simulator_save_files/controlled/NN_short_label/
├── DS30000.sl2          # exact save from Steam/PS4/etc.
└── info.txt             # what just happened, expected flag(s)
```

Naming: zero-padded number then a short snake_case label, e.g.:
- `00_cemetery_of_ash_spawn/`
- `01_iudex_dead/`
- `02_firelink_lit/`
- ...

The number prefix is what sorts them; **do not skip numbers** even if a step turns out trivial — gaps make it harder to follow the diff chain.

## info.txt format

Tiny, structured, free-form. Minimum fields:

```
step: 5
action: killed Vordt of the Boreal Valley
prev: 04_tower_key_bought
expected_flags_set:
  - 13000800  Boss Dead: Vordt of the Boreal Valley
  - 6105      Defeated Boreal Valley Vordt
  - 6301      Boss Victory: Vordt of the Boreal Valley
character: <name>, lvl <N>, <last bonfire>
notes: <anything weird — game crashed, took unexpected action, etc.>
```

Pull flag IDs from `ai_assistant/data/_event_flags.json`. If a step has no good expected-flag match in that file, write `expected_flags_set: <none in wiki list>` — that's fine, it just means we'll discover it.

## Save discipline (critical)

- **Take the save by quitting to main menu** (forces a fresh write). Don't rely on autosave timestamps — Steam Cloud can re-touch the file.
- **Between two checkpoints, take exactly the action listed** — don't talk to extra NPCs, don't light extra bonfires, don't pick up extra items. Every side action adds a flag flip that pollutes the diff.
- **One pickup at a time** for items that drop event flags (Quest Lot flags). E.g. Loretta's Bone is its own checkpoint; don't also grab Charcoal Pine Resin in the same step.
- **Rest at a bonfire before saving** — that flushes pending world state.

---

## The checkpoint sequence

Numbering is loose — if a step is too coarse, split it. If two adjacent steps end up flipping no useful flags, merge them. The goal is *every diff between adjacent steps contains at most ~5 flag flips, and you know which*.

### Stage A — Cemetery of Ash → Firelink (clean boss flags)

These give us the easiest single-flag diffs. Iudex Gundyr and Vordt are forced boss kills with clean flag IDs in the wiki list.

| # | Folder | Action since previous | Expected flag(s) |
|---|---|---|---|
| 00 | `cemetery_of_ash_spawn` | Just created character, before any movement | (baseline — almost no flags set) |
| 01 | `iudex_dead` | Beat Iudex Gundyr | 14000800, 6104, 6319 |
| 02 | `firelink_lit` | Lit Firelink Shrine bonfire, *no NPC dialogue yet* | bonfire-lit flag for Firelink |
| 03 | `talked_andre` | One full dialogue exhaust with Andre | NPC progression flags for Andre |
| 04 | `talked_hawkwood` | One full dialogue exhaust with Hawkwood | NPC progression flags for Hawkwood (50006070-50006074 area) |
| 05 | `talked_handmaid` | One full dialogue exhaust with Shrine Handmaid | NPC progression flags for Handmaid |
| 06 | `talked_ludleth` | One full dialogue exhaust with Ludleth | NPC progression flags for Ludleth (50006031) |
| 07 | `tower_key_bought` | Bought Tower Key from Handmaid (5000 souls) | Tower Key in inventory; Handmaid shop-purchase flag |
| 08 | `vordt_dead` | Beat Vordt of the Boreal Valley | 13000800, 6105, 6301 |
| 09 | `met_emma` | Talked to Emma at top of High Wall (Basin of Vows given) | 1438 (Basin given), 1421/State flags for Emma, 50006230 |
| 10 | `cell_key_picked_up` | Picked up Cell Key from corpse on High Wall rooftop | Cell Key pickup flag |
| 11 | `greirat_freed` | Used Cell Key on Greirat, talked, sent him to Firelink | Greirat NPC state flags |

### Stage B — Undead Settlement: the dense NPC zone

| # | Folder | Action since previous | Expected flag(s) |
|---|---|---|---|
| 12 | `entered_undead_settlement` | Lit Foot of the High Wall bonfire | bonfire-lit flag for Foot of the High Wall |
| 13 | `met_yoel` | Talked to Yoel of Londor at Foot of the High Wall, accepted recruitment | Yoel NPC state flags |
| 14 | `yoel_at_firelink` | Returned to Firelink, talked to Yoel there | Yoel-at-Firelink state flag |
| 15 | `dark_sigil_1` | Yoel "Draw Out True Strength" — 1 free level (must be hollow/unembered) | Dark Sigil count flag(s); 50006193 |
| 16 | `cornyx_freed` | Freed Cornyx from his cage in Undead Settlement | Cornyx NPC state flags; 50006140-50006142 |
| 17 | `cornyx_at_firelink` | Returned to Firelink, talked to Cornyx there | Cornyx-at-Firelink flag |
| 18 | `irina_freed` | Freed Irina with Tower Key (this also spawns Eygon) | Irina + Eygon NPC state flags; 50006160-50006164, 50006170 |
| 19 | `loretta_bone_picked` | Picked up Loretta's Bone (hanging corpse, central Undead Settlement) | Loretta's Bone pickup flag |
| 20 | `loretta_bone_given` | Gave Loretta's Bone to the giant archer in High Wall tower (Hawk Ring drops) | giant-archer state flags; 50006251 |
| 21 | `cliff_underside_bonfire` | Lit Cliff Underside bonfire in Undead Settlement | bonfire-lit flag |
| 22 | `greirat_pillage_1` | Talked to Greirat at Firelink, asked him to pillage Undead Settlement | Greirat-pillaging flag; 50006120 |
| 23 | `greirat_returned_1` | Greirat returned safely (rested several times); collected items | Greirat-pillage-complete flag |
| 24 | `met_anri_horace` | Met Anri + Horace at Halfway Fortress | Anri + Horace NPC state flags |
| 25 | `greatwood_dead` | Killed Curse-Rotted Greatwood (optional boss) | 13100800, 6303, Soul of the Rotted Greatwood, Transposing Kiln in inventory |
| 26 | `kiln_given_to_ludleth` | Gave Transposing Kiln to Ludleth | Ludleth-trades-unlocked flag |
| 27 | `pit_of_hollows` | Entered Pit of Hollows via Greatwood arena drop | Mound-makers covenant access flag |
| 28 | `mound_makers_joined` | Joined Mound-makers covenant from Hodrick | 6710 (Mound-makers Initial Unlock) |

Stop here for the controlled-diff phase. 29 saves, each ~5 minutes of game time, ~2.5 hours total run.

### Stage C — Use the same character to validate ending steering (optional)

If we want a save state that proves the Usurpation ending track is detectable from the parser:
| 29 | `dark_sigil_5` | Continued accepting Yoel levels until 5 Dark Sigils | Yoel-died-with-5-sigils → Yuria-at-Firelink path |
| 30 | `yuria_at_firelink` | Yoel died, Yuria spawned at Firelink | Yuria NPC state flags |

These require getting to Catacombs of Carthus first (Yoel dies after the bonfire there), so they're outside the Undead Settlement scope — defer unless we want to keep going.

---

## After the saves are in

Once Stage A (steps 00 → 11) is captured, **stop and tell me**. Twelve saves with 11 clean diffs in Stage A is *more than enough* to crack the set/unset bit encoding. Then we add the bit decoder to `parser/event_flags.py`, validate it works against Stages B–C, and start writing rules.
