"""Scrape DS3 event flag list from soulsmodding.com → data/_event_flags.json.

Source page (CC BY-SA 4.0):
    https://soulsmodding.com/doku.php?id=ds3-refmat:event-flag-list

This is a one-shot scraper — re-run when the wiki adds/changes flag entries.
Output schema:

    {
      "_source": "<URL>",
      "_license": "CC BY-SA 4.0",
      "_extracted": "<ISO date>",
      "_count": <int>,
      "flags": {
        "<flag_id_as_str>": {"label": "<text>", "category": "<section>"},
        ...
      }
    }

The page is a DokuWiki table. We extract every row that starts with a numeric
flag ID and a label cell. Section headings drive the `category` field.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

URL = "https://soulsmodding.com/doku.php?id=ds3-refmat:event-flag-list"
OUT = Path(__file__).resolve().parent.parent / "data" / "_event_flags.json"

# Match DokuWiki section headers and numeric-ID rows.
_HEADER_RE = re.compile(r"<h([1-4])[^>]*>(.*?)</h\1>", re.S | re.I)
_ROW_RE    = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_CELL_RE   = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)
_TAG_RE    = re.compile(r"<[^>]+>")


def _clean(html: str) -> str:
    return _TAG_RE.sub("", html).replace("&nbsp;", " ").strip()


def scrape(html: str) -> dict[int, dict[str, str]]:
    flags: dict[int, dict[str, str]] = {}
    current_section = "Unknown"
    # Walk top to bottom, alternating between section headers and table rows.
    cursor = 0
    next_header = _HEADER_RE.search(html, cursor)
    next_row = _ROW_RE.search(html, cursor)
    while next_header or next_row:
        if next_header and (not next_row or next_header.start() < next_row.start()):
            current_section = _clean(next_header.group(2)) or current_section
            cursor = next_header.end()
            next_header = _HEADER_RE.search(html, cursor)
        else:
            row_html = next_row.group(1)
            cells = [_clean(c) for c in _CELL_RE.findall(row_html)]
            if len(cells) >= 2 and cells[0].isdigit():
                fid = int(cells[0])
                label = cells[1] or "(no label)"
                flags[fid] = {"label": label, "category": current_section}
            cursor = next_row.end()
            next_row = _ROW_RE.search(html, cursor)
    return flags


def main() -> int:
    print(f"fetching {URL}", file=sys.stderr)
    with urllib.request.urlopen(URL, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    flags = scrape(html)
    if not flags:
        print("no flags parsed — page structure may have changed", file=sys.stderr)
        return 1
    out = {
        "_source": URL,
        "_license": "CC BY-SA 4.0",
        "_extracted": date.today().isoformat(),
        "_count": len(flags),
        "flags": {str(k): flags[k] for k in sorted(flags)},
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"wrote {OUT}  ({len(flags)} flags)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
