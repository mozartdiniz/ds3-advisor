# Advisor & Tips

Current state of the advisor pipeline, reasoner, and the full suggestion catalog for future rules.

---

## Advisor pipeline (session 11 refactor, 2026-06-11)

The advisor is a **hybrid**: a deterministic engine decides *what* is worth
saying (zero tokens); a Claude agent decides *how* to say it, and only runs
when there is something to say. Save events with nothing new cost nothing.

```
save event (watcher.py / play_simulator.py)
   └─ snapshot.py            shared SlotSnap + structured diff (one copy now)
   └─ advisor_core.py        deterministic engine -> Findings
   └─ gate                   no new findings -> silence, zero tokens
   └─ advisor_agent.py       Claude phrases <=2 short messages; the engine's
                             query functions are exposed to it as tools
        fallback             no API key / error -> deterministic text
```

Entry point: `advisor.AdvisorSession(char_key).on_save_event(prev, curr)`.

### Finding sources (advisor_core)

1. **Checkpoints** (`data/checkpoints.json`, replaces tips.json) — each has a
   `policy` that encodes the product philosophy:
   - `retrospective` — surfaced only after the player's furthest progression
     moved *past* the checkpoint's area: "btw, back in Cemetery of Ash you
     missed the Crystal Lizard — here's how to go back." Never pre-hinted.
   - `proactive` — fired the moment the player's progression *reaches* the
     area while the condition is unmet. Reserved for quest-breaking /
     permanently-missable content (Yoel at the pilgrims, Hodrick, Giant
     Archer). This is the only ahead-of-time hint class.
   - `reactive` — fired whenever the condition holds, any area: "you have
     the Cell Key — free Greirat", "you have Loretta's Bone — deliver it."
2. **Quest evaluator** (`decision_making_files/*.json` via
   `quest_evaluator.py`) — `always_check_warnings` become warning findings;
   phase *transitions* (not the first-save baseline) with next_steps become
   info findings.

Progression is a high-water mark over the ordered area list in
checkpoints.json (`max_progression_index`), so resting back at Firelink never
re-opens earlier areas.

### Topics — one message per quest beat, across sources

The checkpoint database and the quest evaluator both know about the same
beats ("deliver Loretta's Bone" exists as a reactive checkpoint, a quest
warning, AND a quest phase), so the same save event used to produce two or
three wordings of the same advice. Fix: an optional `topic` key on
checkpoints (checkpoints.json) and on quest phases/warnings
(decision_making_files). The engine:

1. collapses same-topic findings within one report — highest urgency wins;
   on a tie the hand-written checkpoint text beats generated quest text;
2. records delivered topics in session memory — a topic covered once is
   never resurfaced by ANY source (this also kills cross-step repeats, e.g.
   the quest phase already told the player to find Loretta's Bone, so the
   proactive checkpoint for the same beat stays silent the next save).

Current topics: greirat_free_from_cell, greirat_find_loretta_bone,
greirat_deliver_loretta_bone, greirat_first_outing, irina_free_from_sewer,
yoel_free_levels, yoel_dark_sigils. Findings without a topic default to
their own id (plain once-only dedupe). When adding content that overlaps an
existing beat, tag both sides with the same topic.

### Session memory (`advisor_memory/<char>.json`, gitignored)

Per character: progression high-water mark, delivered finding ids (every
finding fires exactly once), quest phase per questline, last 25 events, last
10 delivered advice titles. The simulator runs with `persist=False`.

### The agent (advisor_agent.py)

- Model `claude-opus-4-8` (override: `DS3_ADVISOR_MODEL`), `max_tokens` 1024,
  system prompt cached (`cache_control: ephemeral`), tool list stable across
  calls so the prompt cache stays warm.
- Tools (SDK `@beta_tool` + `tool_runner`): `get_player_state`,
  `get_quest_status(quest)`, `get_area_checklist(area)`,
  `search_wiki(query)` (keyword search over the 1,289 local wiki markdowns).
- Prompt contract: ≤2 short player-facing messages; quest warnings first,
  then missed content, then quest steps; retrospective tone for missed
  content; no spoilers beyond findings; game facts grounded in findings/tool
  results; skips anything in `recently_delivered`.
- `watcher.py` uses the LLM by default (`--no-llm` to disable);
  `play_simulator.py` is deterministic by default (`--llm` to opt in,
  `--no-advisor` for diff-only).

Validated against the quest-track corpus (12 saves, slot 4): retrospective
checkpoints fire only after leaving the area, Yoel/Hodrick/Giant-Archer
warnings fire on reaching Undead Settlement, reactive quest steps track the
Greirat/Irina/Yoel lines, and the Yuria phase transition fires on step 12
(quest file now keyed to talk flag 74000600 with the shop-stock proxy as
fallback).

### Superseded

- `data/tips.json` + the old `get_tips()` area-scoped matcher — content was
  ported into checkpoints.json with policies; tips.json is kept on disk as
  reference only, nothing loads it.

---

## What the reasoner does today (10 rules)

All single-state predicates over reliably-parsed data (stats, inventory, equipment, last bonfire) — no event flags needed. Regression-tested in `tests/test_reason.py` (crafted slot dicts, no corpus saves required).

| Rule ID | Trigger | What it says |
|---------|---------|-------------|
| `E.int_no_catalyst` | INT ≥ 14 with no staff in inventory | Point player at nearest staff |
| `E.faith_no_chime` | FAITH ≥ 14 with no chime/talisman in inventory | Point player at nearest chime |
| `E.caster_no_flame` | INT ≥ 12 **and** FAITH ≥ 12 (pyromancy spread) but no flame/staff/chime | Point at Cornyx's free Pyromancy Flame |
| `E.low_vigor` | Level ≥ 25 and VIG < 18 | Fragility nudge |
| `E.stat_overinvest` | Any attribute past its effective ceiling (STR/DEX/INT/FTH/LCK 60, VIG 50, END 40) | Wasted-points info |
| `E.ludleth_trades_available` | Boss souls in inventory | List unused boss souls + Ludleth trade options |
| `F.covenant_badges` | Covenant badges in inventory | Report each badge + how it works |
| `H.key_item_nudges` | Key items: Loretta's Bone, Small Doll, Eyes of a Fire Keeper, Storm Ruler, Dark Sigil, Pale Tongue, Old Cell Key, Transposing Kiln, Grave Key | Context-appropriate tip for each |
| `H.area.<area>` | Last bonfire matches one of 11 base-game areas | Missable/lockout nudges; Kiln fires as a `warning` |
| `D.usurpation_path_active` | Dark Sigil present | Flag that Yoel/Yuria path is active (imprecise without hollowing count) |

The "1146" save (lvl 20 with INT 15 / FAITH 22 and no caster gear) triggers genuine prevent-regret advice — first concrete proof the pipeline produces useful output.

---

## Rule-based advisor: zero tokens at runtime

**Architecture**: tips are stored in `data/tips.json` as structured rules. At runtime, `advisor.get_tips(state)` does pure Python condition matching — no LLM call.

### Tip schema

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

### Build detection (from stats)

| Build | Condition |
|-------|-----------|
| `dex` | DEX ≥ 20 and DEX > STR+4 |
| `str` | STR ≥ 20 and STR > DEX+4 |
| `int` | INT ≥ 18 |
| `fth` | FTH ≥ 18 |
| `pyro` | INT ≥ 14 and FTH ≥ 14 |
| `balanced` | otherwise |

### Current tip database (23 tips — session 8)

Covers Cemetery of Ash → Undead Settlement. Sourced from FightinCowboy 100% walkthrough transcript.

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
| *(+ 10 more)* | | | |

Tips fire at exactly the right steps with no false positives across all 40 QA saves and 6 controlled saves.

---

## Play simulator

`play_simulator.py` — replays a folder of numbered `.sl2` saves, copying each to `sim_workspace/DS30000.sl2`, parsing it, and printing what changed + matching tips.

```
python play_simulator.py play_00          # 40-step QA playthrough
python play_simulator.py play_01          # 6 controlled save pairs
python play_simulator.py play_00 --interval 3   # 3s between steps
python play_simulator.py play_00 --no-tips      # diff only, no advisor
```

Key features:
- **Auto slot detection**: compares saves 1 and 2 to find which slot's playtime changed; locks that slot for the whole run.
- **State diff output**: level-ups, location changes, soul gains/losses, inventory in/out, named flag milestones — zero LLM tokens.
- **Advisor integration**: tips shown only when the tip set changes; `[done]` printed when a tip exits scope.

---

## Suggestion catalog (target content: ~120–180 rules)

Rule categories with rough v1 sizing:

| Category | Description | Rule count | Effort |
|---|---|---|---|
| A | Hard lockout warnings (irreversible) | 25–30 | high — per-rule research |
| B | Soft lockouts / "you didn't know there was a quest here" | 20–30 | medium |
| C | Point-of-no-return checklists (Kiln entry, DLC entry, NG+ transition) | 4–6 (each fires many sub-checks) | high |
| D | Ending steering | 6–8 | medium |
| E | Build viability (catalysts/chimes for stats, soft caps, weapon upgrade paths) | 15–20 | low (templated) |
| F | Covenant progression (offering counts, where to farm) | 10–15 | low |
| G | Achievement / completion tracking (extends existing DS1 approach) | auto-derived from CSVs | low |
| H | Event-triggered tips (bonfire lit / boss killed / item gained) | 40–60 | low-medium |

Heavy effort concentrated in A + C + D (~50 rules) — that's the content moat.

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

That's ~50 user-visible rules + automatic achievement tracking. Tractable in 2–3 weekends after the parser+flag-reader are working.
