"""Search entire evens.txt (all sections) for flag IDs."""
import re
from pathlib import Path

text = Path(r"C:\Users\user\Desktop\evens.txt").read_text(encoding="utf-8", errors="ignore")

# Fix: handle both '=== mXX' and '== common...' headers
SECTION_HDR = re.compile(r'={2,3} (\S+)')
EVENT_HDR   = re.compile(r'\$Event\((\d+)')
SET_FLAG    = re.compile(r'SetEventFlag\((\d+),\s*(ON|OFF)\)')
NET_FLAG    = re.compile(r'SetNetworkconnectedEventFlag\((\d+),\s*(ON|OFF)\)')

def section_at(pos):
    """Return the section name for a character position."""
    m = list(SECTION_HDR.finditer(text[:pos]))
    return m[-1].group(1) if m else "?"

def event_at(pos):
    """Return the most recent event ID before pos."""
    m = list(EVENT_HDR.finditer(text[:pos]))
    return m[-1].group(1) if m else "?"

def find_flag(flag_id, call="SetEventFlag"):
    pat = re.compile(call + r'\(' + str(flag_id) + r',')
    results = []
    for m in pat.finditer(text):
        results.append((section_at(m.start()), event_at(m.start()), m.start()))
    return results

# ------------------------------------------------------------------ #
# 1. Our empirically confirmed save-file bit positions
# ------------------------------------------------------------------ #
print("=== Empirically confirmed flags (save analysis) ===\n")
for fid in [29064, 34127, 34085, 34079]:
    r1 = find_flag(fid, "SetEventFlag")
    r2 = find_flag(fid, "SetNetworkconnectedEventFlag")
    all_r = r1 + r2
    if all_r:
        for sec, evt, pos in all_r:
            typ = "SetEventFlag" if (sec, evt, pos) in [(s, e, p) for s, e, p in r1] else "SetNetworkconnectedEventFlag"
            print(f"  flag {fid}: {typ} in event {evt} ({sec})")
    else:
        print(f"  flag {fid}: NOT FOUND anywhere")
print()

# ------------------------------------------------------------------ #
# 2. All SetEventFlag(X, ON) in the common section
# ------------------------------------------------------------------ #
print("=== All unique SetEventFlag(X, ON) in common.emevd.dcx ===\n")
common_start = text.find("== common.emevd.dcx")
if common_start == -1:
    print("  common section NOT FOUND")
else:
    # Find end of common section (next == or end of file)
    next_section = SECTION_HDR.search(text, common_start + 10)
    common_end = next_section.start() if next_section else len(text)
    common_text = text[common_start:common_end]
    print(f"  Common section: lines {text[:common_start].count(chr(10))+1} to {text[:common_end].count(chr(10))+1}")
    print(f"  Size: {len(common_text)} chars\n")

    # Find all SetEventFlag ON in common
    common_flags = {}
    for m in SET_FLAG.finditer(common_text):
        fid = int(m.group(1))
        state = m.group(2)
        if state == "ON":
            evt = event_at(common_start + m.start())
            if fid not in common_flags:
                common_flags[fid] = []
            common_flags[fid].append(evt)

    print(f"  Unique flag IDs with SetEventFlag ON: {len(common_flags)}")
    print()

    # Show all of them sorted
    for fid in sorted(common_flags):
        evts = list(set(common_flags[fid]))
        print(f"  flag {fid:>8}: events {evts[:5]}")

print()

# ------------------------------------------------------------------ #
# 3. Look at event 970 (boss tracker) in common
# ------------------------------------------------------------------ #
print("=== Event 970 (boss tracking event in common.emevd) ===\n")
m = re.search(r'\$Event\(970,', text)
if m:
    end = text.find("$Event(", m.start() + 1)
    evt_text = text[m.start():end if end != -1 else m.start()+3000]
    print(evt_text[:3000])
else:
    print("Event 970 not found")

print()
# ------------------------------------------------------------------ #
# 4. Full file: all SetEventFlag in range 29000-35000 (our empirical range)
# ------------------------------------------------------------------ #
print("=== All SetEventFlag ON in range 25000-40000 (our empirical flag range) ===\n")
count = 0
for m in SET_FLAG.finditer(text):
    fid = int(m.group(1))
    state = m.group(2)
    if state == "ON" and 25000 <= fid <= 40000:
        sec = section_at(m.start())
        evt = event_at(m.start())
        print(f"  flag {fid}: event {evt} ({sec})")
        count += 1
if count == 0:
    print("  NONE FOUND in 25000-40000 range")
