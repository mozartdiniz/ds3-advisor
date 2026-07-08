# MVP Validation Run — Checklist (up to the Abyss Watchers)

Guide for the live validation run. Play normally — "dirty" saves are part of the test.
Tick each box as you complete it. When the advisor speaks, note ✔ (spoke correctly), ✖ (didn't speak / spoke wrong) or 🕐 (spoke at an odd time) next to the item.

**How to validate afterwards:** each "🔔 Expected" item cites the checkpoint/quest id — you can grep the session log for it (`checkpoint:<id>` / `quest:<id>`).

---

## 0. Setup (before launching the game)

- [x] Terminal in `ai_assistant/`, venv activated (or use `venv\Scripts\python.exe`)
- [x] `$env:DS3_SAVE_PATH = "$env:APPDATA\DarkSoulsIII\<your-steam-id>"`
- [x] `$env:ANTHROPIC_API_KEY` set (this run doubles as the live LLM test; for a deterministic baseline run with `--no-llm` instead)
- [x] **`python watcher.py --record`** ← `--record` is mandatory: it archives every save into `play_NN_auto/` + a session log for the validation replay afterwards
- [x] NEW character. Any class; suggestion: a class with INT ≥ 10 makes Orbeck easier (Assassin 11, Thief/Mercenary 10) — otherwise plan to level INT to 10 by mid-run
- [x] Note here the folder the watcher created: `play____auto`

> Mechanics reminder: the advisor only speaks when the game SAVES — rest at a bonfire or die to "commit" each step. At points marked 💾, rest on purpose.

---

## 1. Cemetery of Ash

- [x] **DELIBERATE TEST — skip the Crystal Lizard** (don't kill it; we move on without the Titanite Scale)
- [x] Iudex Gundyr dead 💾
- [x] Reach Firelink, light the bonfire 💾
  - 🔔 Expected once progression moves past the Cemetery: retrospective `cemetery_crystal_lizard` ("Missed: Titanite Scale...")

## 2. Firelink Shrine (first visit)

- [x] Talk to the Fire Keeper, Handmaid, Ludleth, Hawkwood, Leonhard (Leonhard gives Cracked Red Eye Orbs)
  - 🔔 Expected after talking to Leonhard 💾: reactive `firelink_leonhard_questline` (flag 74000850)
- [x] Level up a few times
  - 🔔 Expected once level ≥ 20 (may take a while): `firelink_tower_key` (Estus upgrade)

## 3. High Wall of Lothric

- [x] 💾 at the first High Wall bonfire
  - 🔔 Expected (proactive, on reaching the area): `high_wall_emma_banner` (Emma / banner)
- [x] Grab the **Cell Key** (staircase behind the powder barrels with dogs) — 💾 BEFORE freeing Greirat
  - 🔔 Expected: reactive `high_wall_free_greirat` ("You have the Cell Key - free Greirat")
- [x] Free Greirat, accept his request (Blue Tearstone Ring) 💾
- [x] Build items: Claymore (dragon bridge) and/or Deep Battle Axe (mimic) — grab them OR deliberately skip and watch for the retrospective later (`high_wall_claymore` / `high_wall_deep_battle_axe`, build-dependent)
- [x] Emma: receive Small Lothric Banner + Way of Blue
- [x] Vordt dead 💾

## 4. Undead Settlement — part 1

- [x] 💾 at the Foot of the High Wall bonfire BEFORE talking to Yoel
  - 🔔 Expected (proactive, critical): `undead_settlement_yoel` ("Don't miss Yoel among the dying pilgrims")
- [x] **Talk to Yoel** among the pilgrims, accept → he moves to Firelink
- [x] Loretta's Bone (hanging corpse on the first building's balcony)
  - 🔔 Expected before picking it up (proactive with Blue Tearstone in inventory): `undead_settlement_loretta_bone`
- [x] Estus Shard (plaza bonfire area) and Warrior of Sunlight (hole in the floor of the big building)
- [x] **Cornyx**: free him from the cage 💾 (pyromancy vendor; flag 74000450 at Firelink later)

## 5. Firelink — mid-run errands

- [x] Deliver **Loretta's Bone** to Greirat 💾
  - 🔔 Expected: topic `greirat_deliver_loretta_bone` (reactive with the bone in hand; flag 74000300 confirms delivery)
- [x] **Yoel: "Draw Out True Strength" — 1st sigil** 💾
  - 🔔 Expected: `firelink_yoel_free_levels` + Usurpation path notice (`firelink_dark_sigil_warning`)
  - ⚠️ RUN RULE: all 5 sigils must be drawn BEFORE the Abyss Watchers. Hollowing gates: 2nd sigil = 2 hollowing, 3rd = 6, 4th = 12, 5th = 15. **Die unembered naturally and return to Yoel at each gate.** Track here: [x]1 [x]
  2 [x]3 [x]4 [x]5

## 6. Undead Settlement — part 2

- [x] **Siegward** at the tower elevator; platform trick; **kill the Fire Demon with him** and talk until he toasts you with a Siegbräu 💾 (flag 73100363)
  - 🔔 Expected beforehand (proactive): `undead_settlement_siegward_elevator`
- [x] **Giant in the tower**: talk and receive the pact (friendly arrows)
  - 🔔 Expected beforehand (proactive): `undead_settlement_giant_archer`
- [x] **Mortician's Ashes** in the graveyard covered by the arrows
- [x] **Mound-makers**: talk to the cage carrier, climb into the cage → Hodrick (do NOT kill him) 💾
  - 🔔 Expected beforehand (proactive): `undead_settlement_hodrick_covenant`
- [x] Chloranthy Ring (well drop) + build items (Butcher Knife if STR — `undead_settlement_butcher_knife`)
- [x] **Curse-Rotted Greatwood** dead → Transposing Kiln 💾
  - 🔔 Expected: `firelink_give_transposing_kiln` (Kiln in inventory)

## 7. Firelink — post-Greatwood

- [x] Give the Kiln to Ludleth
- [x] **Send Greirat scavenging** (first outing, safe) 💾
  - 🔔 Expected: topic `greirat_first_outing` (flag 74000302 confirms the send-off)
- [x] Mortician's Ashes → Handmaid → buy the **Grave Key** (1,500) 💾
  - 🔔 Expected: reactive `undead_settlement_irina_sewer` ("You have the Grave Key")
- [x] Sewers below the Dilapidated Bridge → **Irina** (accept her service) + Eygon 💾 (flags 73100100/73100300)

## 8. Road of Sacrifices

- [x] 💾 at the first bonfire in the area
  - 🔔 Expected (proactive batch for the area — judge whether the volume is annoying): `road_halfway_anri_horace`, `road_farron_coal`, `road_orbeck_recruit`, `farron_keep_checklist` (this one talks about Farron ahead of time — note your impression of the timing) + Sirris phase ("waits at Firelink")
- [ ] **DELIBERATE TEST — do NOT pick up yet** the Braille Divine Tome of Carim (cliff platform before the bridge). We'll let the retrospective fire post-Cathedral and come back later
- [ ] **Halfway Fortress: talk to Anri and Horace** (receive Blue Sentinels) 💾
- [ ] **Farron Coal** (drop-down right of Halfway, the Black Knight corridor)
- [ ] Crab water: **Grass Crest Shield** + **Great Swamp Pyromancy Tome** (+ Great Swamp Ring if you kill the big crab)
- [ ] Exiles at the Farron entrance: Exile Greatsword / Great Club (if STR)
- [x] **Orbeck** (2nd floor of the flooded room before the boss) — INT ≥ 10! 💾
- [ ] Back to Firelink: coal → **Andre**; talk to **Sirris**; Great Swamp tome → **Cornyx**; sorceries + scroll not yet (the scrolls come in Farron)
- [x] **Crystal Sage** dead 💾 (flag 13300850)

## 9. Cathedral of the Deep

- [x] **Paladin's Ashes** at the start (otherwise: retrospective `cathedral_paladins_ashes` later)
- [ ] 💾 at the Cleansing Chapel
  - 🔔 Expected (area proactives): `cathedral_patches_arrival` (don't kill Patches), `cathedral_siegward_well` (well left of the chapel — only if flag 73100363 is set ✓), `cathedral_rosaria_chamber`
- [ ] **Patches** events (bridge/disguise) — do NOT kill him
- [ ] First **Pale Tongue** that drops (Kirk invades here) 💾
  - 🔔 Expected: `cathedral_pale_tongue_sirris` ("do NOT offer them to Rosaria yet")
- [ ] **Deep Braille Divine Tome** (mimic on the lower path) 💾
  - 🔔 Expected: Irina warning `warn_dark_tome_about_to_be_given` (DARK tome — do not give it to Irina!)
- [ ] **Rosaria**: join (respec/appearance is safe; do NOT offer a tongue)
- [ ] **Deacons of the Deep** dead → Small Doll 💾 (flag 13500800)
  - 🔔 Expected at the next rest: **`abyss_watchers_prep`** — the gate: Yoel's 5 sigils + Orbeck's scroll. THIS IS THE MOST IMPORTANT TEST OF THE RUN.

## 10. Firelink — post-Deacons

- [ ] **Anri & Horace at Firelink** — talk to both 💾 (phase `post_deacons_firelink`)
- [ ] **Patches at Firelink** → buy the **full Catarina Set** 💾
  - 🔔 Expected: Siegward phase `armor_in_hand` ("return it at the Cathedral well")
- [ ] Back to the Cathedral well → **return the armor to Siegward** 💾
  - ⚠️ No flag for this yet — note what the advisor says after the hand-over (expected: the `demon_fight_done` phase should NOT re-fire since it was already delivered once; confirm there's no duplicate message)
- [ ] Check the sigil counter (item 5) — if any are missing, die unembered and return to Yoel

## 11. Farron Keep

- [ ] 💾 at the Farron Keep bonfire
- [ ] **Sage's Scroll** (Keep Ruins region) and **Golden Scroll** (cave in the south of the swamp, next to the Antiquated Set) 💾
  - 🔔 Expected with a scroll in hand + Deacons dead: Orbeck warning `warn_scroll_undelivered` + phase `scroll_in_hand`
- [ ] The 3 flames extinguished; **Old Wolf bonfire** → Watchdogs of Farron; Dreamchaser's Ashes; 2 Undead Bone Shards; Lightning Spear (if FTH); Stray Demon (soul for Havel's Ring)
- [ ] **DELIBERATE TEST — Carim tome retrospective**: by now (Cathedral behind us) the retrospective `road_braille_tome_carim` should have fired. Go back to the Road, grab the tome + Morne's Ring following the warning's "where" text and judge whether the instructions work. Give the tome to Irina (it's LIGHT, safe)
- [ ] Firelink: **give ONE scroll to Orbeck** 💾; buy 3 sorceries → **Young Dragon Ring** 💾
  - 🔔 Expected: phase `scroll_given_ring_proxy` ("Orbeck is settled")

## 12. Final gate — PRE-Abyss Watchers

- [ ] ✅ Sigils: 5/5 (if not: do NOT kill the boss yet)
- [ ] ✅ Scroll delivered to Orbeck
- [ ] ✅ Armor returned to Siegward
- [ ] ✅ Anri/Horace talked to at Firelink
- [ ] Re-read what `abyss_watchers_prep` said — does it match this checklist?

## 13. Abyss Watchers 💾 (flag 13300800)

- [ ] Boss dead — rest
- [ ] Firelink: **Yoel should be dead**; with 5 sigils, **Yuria appears** — talk to her 💾 (flag 74000600)
  - 🔔 Expected: Yoel/Yuria phase (`yuria_active`) + the CRITICAL rules (don't heal the Dark Sigil etc.)
- [ ] Talk to Hawkwood/Ludleth, note any odd advisor message

## 14. Wrap-up

- [ ] Ctrl+C the watcher; note the `play_NN_auto` folder and the `session_*.log` file
- [ ] Dump general observations here (wrong, missing or duplicated messages, tone, timing, volume):

```
(run notes)
```

---

## After the run (we'll do this together)

1. Deterministic replay: `python play_simulator.py play_NN_auto --interval 0` and diff against this checklist
2. Every ✖/🕐 noted becomes a detection/text fix
3. The run's saves double as free controlled saves for labelling the `readable:false` flags (Orbeck recruited/scroll given, Anri/Sirris talks, armor returned — see the quest files' `flag_registry`)
