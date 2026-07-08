"""advisor_core.py - deterministic advisor engine. Zero LLM tokens.

Turns a save event (prev snapshot -> curr snapshot) into a list of Findings:

  * retrospective checkpoints - content the player missed in an area they have
    now progressed PAST ("btw, you missed X back in <area>")
  * proactive checkpoints     - quest-break prevention, fired as soon as the
    risk window opens (the only case where we hint ahead of time)
  * reactive checkpoints      - "you have item X, now do Y" quest steps
  * quest evaluator output    - phase transitions + always-check warnings from
    decision_making_files/*.json

Per-character session memory (progression high-water mark, delivered finding
ids, quest phases, recent events) makes every finding fire exactly once.

The same module exposes the query helpers the LLM agent uses as tools:
state summary, quest status, area checklist, wiki search.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from parser.flags import KNOWN_FLAGS
from snapshot import SlotSnap, diff_events
import quest_evaluator

AI_DIR          = Path(__file__).resolve().parent
DATA_DIR        = AI_DIR / "data"
QUEST_DIR       = AI_DIR / "decision_making_files"
MEMORY_DIR      = AI_DIR / "advisor_memory"
WIKI_DIR        = AI_DIR.parent / "data" / "wiki"
CHECKPOINTS_PATH = DATA_DIR / "checkpoints.json"

URGENCY_ORDER = {"warning": 0, "reminder": 1, "info": 2}


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    id: str                 # stable dedupe key
    kind: str               # missed_content | quest_warning | quest_step | quest_phase
    urgency: str            # warning | reminder | info
    title: str
    detail: str
    area: Optional[str] = None
    topic: Optional[str] = None    # same beat across sources shares a topic;
                                   # one message per topic, ever (None = id)
    source: str = "checkpoint"     # checkpoint | quest

    @property
    def effective_topic(self) -> str:
        return self.topic or self.id

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("topic", None)
        d.pop("source", None)
        return d


# ---------------------------------------------------------------------------
# Build detection (from stats)
# ---------------------------------------------------------------------------

def detect_build(stats: dict[str, int]) -> list[str]:
    builds = []
    s = stats.get("str", 10)
    d = stats.get("dex", 10)
    i = stats.get("int", 10)
    f = stats.get("fth", 10)

    if d >= 20 and d > s + 4:
        builds.append("dex")
    if s >= 20 and s > d + 4:
        builds.append("str")
    if i >= 18:
        builds.append("int")
    if f >= 18:
        builds.append("fth")
    if i >= 14 and f >= 14:
        builds.append("pyro")
    if not builds:
        builds.append("balanced")
    return builds


# ---------------------------------------------------------------------------
# Checkpoint database
# ---------------------------------------------------------------------------

def _load_checkpoints() -> dict:
    return json.loads(CHECKPOINTS_PATH.read_text(encoding="utf-8"))


def _area_index(progression: list[str], area_name: Optional[str]) -> Optional[int]:
    if not area_name:
        return None
    for i, a in enumerate(progression):
        if a.lower() == area_name.lower():
            return i
    return None


def _detection_met(det: dict, snap: SlotSnap) -> bool:
    """True if every detection condition holds (i.e. the checkpoint is LIVE -
    the action has not been done / the content is still missing)."""
    inv_lower = {k.lower() for k in snap.inventory}

    for item in det.get("has_items") or []:
        if item.lower() not in inv_lower:
            return False
    for item in det.get("missing_items") or []:
        if item.lower() in inv_lower:
            return False
    for fid in det.get("has_flags") or []:
        if fid not in snap.flags_set:
            return False
    for fid in det.get("missing_flags") or []:
        if fid in snap.flags_set:
            return False

    builds = det.get("builds")
    if builds:
        if not any(b in detect_build(snap.stats) for b in builds):
            return False

    min_level = det.get("min_level")
    if min_level is not None and snap.level < min_level:
        return False

    return True


# ---------------------------------------------------------------------------
# Session memory (per character)
# ---------------------------------------------------------------------------

class SessionMemory:
    """Per-character advisor memory. Persisted as one JSON file per character
    unless persist=False (used by the play simulator)."""

    def __init__(self, char_key: str, persist: bool = True):
        self.char_key = char_key
        self.persist = persist
        self.path = MEMORY_DIR / (re.sub(r"[^A-Za-z0-9_-]", "_", char_key) + ".json")
        self.data = {
            "max_progression_index": -1,
            "delivered": [],          # finding ids already shown to the player
            "delivered_topics": [],   # topics already covered (any source)
            "quest_phases": {},       # quest_id -> phase id
            "recent_events": [],      # last N diff event strings
            "recent_advice": [],      # last N delivered finding titles
        }
        if persist and self.path.exists():
            try:
                self.data.update(json.loads(self.path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                pass

    def save(self) -> None:
        if not self.persist:
            return
        MEMORY_DIR.mkdir(exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    @property
    def delivered(self) -> set[str]:
        return set(self.data["delivered"])

    @property
    def delivered_topics(self) -> set[str]:
        return set(self.data.get("delivered_topics", []))

    def mark_delivered(self, findings: list[Finding]) -> None:
        for f in findings:
            if f.id not in self.data["delivered"]:
                self.data["delivered"].append(f.id)
            topic = f.effective_topic
            if topic not in self.data.setdefault("delivered_topics", []):
                self.data["delivered_topics"].append(topic)
            self.data["recent_advice"] = (self.data["recent_advice"] + [f.title])[-10:]

    def push_events(self, events: list[str]) -> None:
        self.data["recent_events"] = (self.data["recent_events"] + events)[-25:]


def _dedupe_by_topic(findings: list["Finding"]) -> list["Finding"]:
    """Keep one finding per topic within a report.

    The checkpoint database and the quest evaluator both know about the same
    quest beats (e.g. "deliver Loretta's Bone"), so the same save event can
    yield two or three wordings of one piece of advice. Findings that share a
    topic are collapsed to the best one: highest urgency wins; on a tie the
    hand-written checkpoint text is preferred over generated quest text.
    """
    ranked = sorted(findings, key=lambda f: (
        URGENCY_ORDER.get(f.urgency, 2),
        0 if f.source == "checkpoint" else 1,
    ))
    seen: set[str] = set()
    kept: list[Finding] = []
    for f in ranked:
        topic = f.effective_topic
        if topic in seen:
            continue
        seen.add(topic)
        kept.append(f)
    return kept


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

@dataclass
class AdvisorReport:
    events: list[str]                       # what changed in this save
    findings: list[Finding]                 # NEW findings (deduped), urgency-sorted
    quest_phase_changes: list[dict]         # context: quest phase transitions
    snapshot: SlotSnap = field(repr=False, default=None)
    memory: SessionMemory = field(repr=False, default=None)


class AdvisorEngine:
    def __init__(self):
        db = _load_checkpoints()
        self.progression: list[str] = db["progression"]
        self.checkpoints: list[dict] = db["checkpoints"]
        self.quests: list[dict] = [
            quest_evaluator.load_quest(p) for p in sorted(QUEST_DIR.glob("*.json"))
        ]

    # -- snapshot adapter for quest_evaluator (expects extract.py-shaped dict)
    @staticmethod
    def _slot_dict(snap: SlotSnap) -> dict:
        return {
            "inventory": [{"name": n} for n in snap.inventory],
            "equipment": [{"name": n} for n in snap.equipment.values()],
            "flags_set": {KNOWN_FLAGS[fid]: True for fid in snap.flags_set
                          if fid in KNOWN_FLAGS},
            "last_bonfire_name": snap.bonfire_name,
        }

    # -- main entry -----------------------------------------------------------
    def process(self, prev: Optional[SlotSnap], curr: SlotSnap,
                memory: SessionMemory) -> AdvisorReport:
        events = diff_events(prev, curr)
        memory.push_events(events)

        # progression high-water mark
        cur_idx = _area_index(self.progression, curr.bonfire_name)
        max_idx = memory.data["max_progression_index"]
        if cur_idx is not None and cur_idx > max_idx:
            max_idx = cur_idx
            memory.data["max_progression_index"] = max_idx

        findings: list[Finding] = []
        delivered = memory.delivered
        delivered_topics = memory.delivered_topics

        # 1. checkpoints
        for cp in self.checkpoints:
            fid = "checkpoint:" + cp["id"]
            if fid in delivered or (cp.get("topic") or fid) in delivered_topics:
                continue
            area_idx = _area_index(self.progression, cp.get("area"))
            policy = cp["policy"]

            if policy == "retrospective":
                in_window = area_idx is not None and max_idx > area_idx
            elif policy == "proactive":
                in_window = area_idx is not None and max_idx >= area_idx
            else:  # reactive
                in_window = True

            if not in_window or not _detection_met(cp.get("detection", {}), curr):
                continue

            detail = cp["detail"]
            if cp.get("where"):
                detail += " How to get back: " + cp["where"]
            kind = {"retrospective": "missed_content",
                    "proactive": "quest_warning",
                    "reactive": "quest_step"}[policy]
            findings.append(Finding(
                id=fid, kind=kind, urgency=cp.get("urgency", "info"),
                title=cp["title"], detail=detail, area=cp.get("area"),
                topic=cp.get("topic"), source="checkpoint",
            ))

        # 2. quest evaluator: warnings + phase transitions
        slot = self._slot_dict(curr)
        phase_changes: list[dict] = []
        for quest in self.quests:
            result = quest_evaluator.evaluate_quest(quest, slot)
            qid = result["quest_id"]

            for warning in result["active_warnings"]:
                fid = f"quest:{qid}:{warning['id']}"
                if fid in delivered or \
                        (warning.get("topic") or fid) in delivered_topics:
                    continue
                findings.append(Finding(
                    id=fid, kind="quest_warning",
                    urgency=warning.get("urgency", "warning"),
                    title=f"{result['npc']}: {warning['label']}",
                    detail=warning["message"],
                    topic=warning.get("topic"), source="quest",
                ))

            phase = result.get("active_phase")
            if phase:
                prev_phase = memory.data["quest_phases"].get(qid)
                if prev_phase != phase["id"]:
                    memory.data["quest_phases"][qid] = phase["id"]
                    change = {
                        "quest": result["npc"],
                        "from": prev_phase,
                        "to": phase["id"],
                        "label": phase["label"],
                        "status": phase["status_message"],
                        "next_steps": phase.get("next_steps", []),
                    }
                    phase_changes.append(change)

                    # A real transition (not the first-save baseline) with
                    # next steps is worth a gentle quest-step nudge.
                    if prev_phase is not None and phase.get("next_steps") \
                            and not phase.get("terminal"):
                        fid = f"quest:{qid}:phase:{phase['id']}"
                        if fid not in delivered and \
                                (phase.get("topic") or fid) not in delivered_topics:
                            findings.append(Finding(
                                id=fid, kind="quest_phase", urgency="info",
                                title=f"{result['npc']}: {phase['label']}",
                                detail=phase["status_message"] + " Next: " +
                                       " - ".join(phase["next_steps"]),
                                topic=phase.get("topic"), source="quest",
                            ))

        findings = _dedupe_by_topic(findings)
        findings.sort(key=lambda f: URGENCY_ORDER.get(f.urgency, 2))
        return AdvisorReport(events=events, findings=findings,
                             quest_phase_changes=phase_changes,
                             snapshot=curr, memory=memory)

    # -- query helpers (exposed to the LLM agent as tools) --------------------

    def state_summary(self, snap: SlotSnap) -> str:
        key_items = [n for n in sorted(snap.inventory)
                     if any(k in n for k in (
                         "Key", "Bone", "Ashes", "Banner", "Sigil", "Kiln",
                         "Tome", "Soul of", "Doll", "Tearstone", "Siegbr",
                         "Scroll", "Coal"))]
        flags = [KNOWN_FLAGS[f] for f in sorted(snap.flags_set) if f in KNOWN_FLAGS]
        s = snap.stats
        return "\n".join([
            f"Character: {snap.name}  Level {snap.level}  Souls {snap.souls:,}",
            f"Build: {', '.join(detect_build(s))}  "
            f"(VIG {s.get('vigor')}, STR {s.get('str')}, DEX {s.get('dex')}, "
            f"INT {s.get('int')}, FTH {s.get('fth')})",
            f"Last bonfire: {snap.bonfire_name or snap.bonfire_id}",
            "Key items: " + (", ".join(key_items) or "(none)"),
            "Quest/boss flags set: " + ("; ".join(flags) or "(none)"),
        ])

    def quest_status(self, quest_id: str, snap: SlotSnap) -> str:
        slot = self._slot_dict(snap)
        for quest in self.quests:
            qid = quest.get("_meta", {}).get("quest_id", "")
            if quest_id.lower() in qid.lower() or \
               quest_id.lower() in quest.get("_meta", {}).get("npc", "").lower():
                result = quest_evaluator.evaluate_quest(quest, slot)
                return quest_evaluator.format_result(result)
        known = [q.get("_meta", {}).get("quest_id", "?") for q in self.quests]
        return f"Unknown quest '{quest_id}'. Known quests: {', '.join(known)}"

    def area_checklist(self, area: str, snap: SlotSnap) -> str:
        lines = [f"Checkpoints for {area}:"]
        for cp in self.checkpoints:
            if cp.get("area", "").lower() != area.lower():
                continue
            live = _detection_met(cp.get("detection", {}), snap)
            status = "OPEN (not done / still missing)" if live else "done or not applicable"
            lines.append(f"- [{cp['policy']}/{cp['urgency']}] {cp['title']} -> {status}")
        if len(lines) == 1:
            lines.append("(no checkpoints recorded for this area)")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Wiki search (lazy in-memory index over data/wiki/*.md)
# ---------------------------------------------------------------------------

_WIKI_INDEX: Optional[list[tuple[str, str]]] = None   # (name_lower, text_lower)
_WIKI_FILES: list[Path] = []


def _wiki_index() -> list[tuple[str, str]]:
    global _WIKI_INDEX, _WIKI_FILES
    if _WIKI_INDEX is None:
        _WIKI_INDEX = []
        _WIKI_FILES = sorted(WIKI_DIR.glob("*.md")) if WIKI_DIR.exists() else []
        for p in _WIKI_FILES:
            try:
                _WIKI_INDEX.append((p.stem.lower(), p.read_text(
                    encoding="utf-8", errors="ignore").lower()))
            except OSError:
                _WIKI_INDEX.append((p.stem.lower(), ""))
    return _WIKI_INDEX


def search_wiki(query: str, max_results: int = 3, snippet_chars: int = 1200) -> str:
    """Keyword search over the local DS3 wiki dump. Returns top page snippets."""
    index = _wiki_index()
    if not index:
        return "(wiki corpus not found on disk)"
    terms = [t for t in re.split(r"[^a-z0-9']+", query.lower()) if len(t) > 2]
    if not terms:
        return "(query too short)"

    scored = []
    for i, (name, text) in enumerate(index):
        score = sum(10 for t in terms if t in name)
        score += sum(min(text.count(t), 20) for t in terms)
        if score > 0:
            scored.append((score, i))
    scored.sort(reverse=True)

    out = []
    for _, i in scored[:max_results]:
        path = _WIKI_FILES[i]
        text = path.read_text(encoding="utf-8", errors="ignore")
        # snippet around the first term occurrence
        low = text.lower()
        pos = min((low.find(t) for t in terms if low.find(t) >= 0), default=0)
        start = max(0, pos - 200)
        snippet = text[start:start + snippet_chars].strip()
        out.append(f"=== {path.stem} ===\n{snippet}")
    return "\n\n".join(out) if out else "(no wiki pages matched)"


# ---------------------------------------------------------------------------
# Deterministic rendering (fallback when no LLM is used)
# ---------------------------------------------------------------------------

ICONS = {"warning": "[!]", "reminder": "[>]", "info": "[i]"}


def format_findings(findings: list[Finding], max_items: int = 5) -> str:
    if not findings:
        return ""
    lines = []
    for f in findings[:max_items]:
        lines.append("%s %s" % (ICONS.get(f.urgency, "[i]"), f.title))
        lines.append("    %s" % f.detail)
    if len(findings) > max_items:
        lines.append("    ... (%d more)" % (len(findings) - max_items))
    return "\n".join(lines)
