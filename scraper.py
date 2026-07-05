#!/usr/bin/env python3
"""Dark Souls 3 wiki scraper — fextralife.com → CSV files per item category."""

import csv
import time
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://darksouls3.wiki.fextralife.com"
OUT_DIR = Path("data")
OUT_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# Categories where only the largest table on the page should be kept.
# (Other pages mix multiple tables that are all part of the same item list.)
LARGEST_TABLE_ONLY = {
    "sorceries", "miracles", "pyromancies",
}

CATEGORIES = {
    # Weapons
    "daggers":              "/Daggers",
    "straight_swords":      "/Straight+Swords",
    "greatswords":          "/Greatswords",
    "ultra_greatswords":    "/Ultra+Greatswords",
    "curved_swords":        "/Curved+Swords",
    "katanas":              "/Katanas",
    "curved_greatswords":   "/Curved+Greatswords",
    "piercing_swords":      "/Piercing+Swords",
    "axes":                 "/Axes",
    "greataxes":            "/Greataxes",
    "hammers":              "/Hammers",
    "great_hammers":        "/Great+Hammers",
    "fist_claws":           "/Fist+&+Claws",
    "spears_pikes":         "/Spears+&+Pikes",
    "halberds":             "/Halberds",
    "reapers":              "/Reapers",
    "whips":                "/Whips",
    "bows":                 "/Bows",
    "greatbows":            "/Greatbows",
    "crossbows":            "/Crossbows",
    "boss_soul_weapons":    "/Boss+Soul+Weapons",
    # Catalysts
    "staves":               "/Staves",
    "flames":               "/Flames",
    "talismans":            "/Talismans",
    "sacred_chimes":        "/Sacred+Chimes",
    # Shields (main page has no table; scrape sub-pages)
    "small_shields":        "/Small+Shields",
    "standard_shields":     "/Standard+Shields",
    "greatshields":         "/Greatshields",
    # Armor
    "helms":                "/Helms",
    "chest_armor":          "/Chest+Armor",
    "gauntlets":            "/Gauntlets",
    "leg_armor":            "/Leg+Armor",
    # Rings — required for "Master of Rings" achievement
    "rings":                "/Rings",
    # Magic — required for spell-master achievements
    "sorceries":            "/Sorceries",
    "pyromancies":          "/Pyromancies",
    "miracles":             "/Miracles",
    # Items
    "consumables":          "/Consumables",
    "key_items":            "/Key+Items",
    "multiplayer_items":    "/Multiplayer+Items",
    "tools":                "/Tools",
    "ammunition":           "/Ammunition",
    "upgrade_materials":    "/Upgrade+Materials",
    "ashes":                "/Ashes",
    "boss_souls":           "/Boss+Souls",
    # Gestures — required for "Master of Expression" achievement
    "gestures":             "/Gestures",
}

ICON_HEADER_MAP = {
    "spellslot":        "Attunement Slots",
    "attunement slots": "Attunement Slots",
    "attunement":       "Attunement Slots",
    "slots":            "Attunement Slots",
    "intelligence":     "Intelligence",
    "icon_int":         "Intelligence",
    "int":              "Intelligence",
    "faith":            "Faith",
    "icon_fth":         "Faith",
    "fth":              "Faith",
    "fp cost":          "FP Cost",
    "fp":               "FP Cost",
    "str":              "Strength",
    "strength":         "Strength",
    "icon_str":         "Strength",
    "dex":              "Dexterity",
    "dexterity":        "Dexterity",
    "icon_dex":         "Dexterity",
    "luck":             "Luck",
    "icon_lck":         "Luck",
    # Armor defense stats
    "physicaldef":      "Physical Def",
    "strikedef":        "Strike Def",
    "slashdef":         "Slash Def",
    "thrustdef":        "Thrust Def",
    "magicdef":         "Magic Def",
    "firedef":          "Fire Def",
    "lightningdef":     "Lightning Def",
    "darkdef":          "Dark Def",
    "bleedres":         "Bleed Res",
    "poisonres":        "Poison Res",
    "frostres":         "Frost Res",
    "curseres":         "Curse Res",
    "res_poise":        "Poise",
    "poise":            "Poise",
    "weight":           "Weight",
    "durabili":         "Durability",
    # Weapon stats
    "physical":         "Physical ATK",
    "critical":         "Critical",
    "stability":        "Stability",
    "fp":               "FP Cost",
    "fpattack":         "FP Cost",
}


def fetch(path: str) -> BeautifulSoup:
    url = BASE_URL + path
    print(f"  GET {url}")
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    time.sleep(1.5)
    return BeautifulSoup(resp.text, "html.parser")


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def resolve_icon_header(th) -> str:
    text = clean(th.get_text())
    if text:
        return text
    img = th.find("img")
    if img:
        for attr in ("alt", "title", "data-src", "src"):
            val = (img.get(attr) or "").lower()
            for key, label in ICON_HEADER_MAP.items():
                if key in val:
                    return label
    span = th.find("span")
    if span:
        val = (span.get("title") or span.get_text() or "").lower()
        for key, label in ICON_HEADER_MAP.items():
            if key in val:
                return label
    return ""


def table_to_rows(table) -> tuple[list[str], list[dict]]:
    headers = []
    rows = []
    has_thead = False

    thead = table.find("thead")
    if thead:
        has_thead = True
        # fextralife uses <td> in <thead> instead of <th>
        ths = thead.find_all(["th", "td"])
        headers = [resolve_icon_header(th) for th in ths]
    else:
        first_tr = table.find("tr")
        if first_tr:
            ths = first_tr.find_all(["th", "td"])
            headers = [resolve_icon_header(th) for th in ths]

    headers = [h if h else f"col_{i}" for i, h in enumerate(headers)]
    if not headers:
        return headers, rows

    tbody = table.find("tbody") or table
    all_trs = tbody.find_all("tr")
    # When there's no <thead>, the first <tr> is the header row — skip it
    if not has_thead and all_trs:
        all_trs = all_trs[1:]

    for tr in all_trs:
        cells = tr.find_all(["td", "th"])
        if not cells:
            continue
        if all(c.name == "th" for c in cells):
            continue
        values = [clean(c.get_text()) for c in cells]
        while len(values) < len(headers):
            values.append("")
        row = dict(zip(headers, values[: len(headers)]))
        if any(v for v in row.values()):
            rows.append(row)

    return headers, rows


def scrape_gestures(soup: BeautifulSoup) -> tuple[list[str], list[dict]]:
    headers: list[str] = []
    rows: list[dict] = []
    for table in soup.find_all("table"):
        h, r = table_to_rows(table)
        if r:
            for col in h:
                if col not in headers:
                    headers.append(col)
            rows.extend(r)
    return headers, rows


def scrape_category(name: str, path: str) -> None:
    print(f"\n[{name}]")
    soup = fetch(path)

    if name == "gestures":
        headers, all_rows = scrape_gestures(soup)
    else:
        tables = soup.find_all("table")
        if not tables:
            print(f"  no tables found on {path}")
            return

        all_headers: list[str] = []
        all_rows: list[dict] = []

        if name in LARGEST_TABLE_ONLY:
            # Parse all tables, keep only the one with the most rows
            candidates = [(table_to_rows(t)) for t in tables]
            candidates = [(h, r) for h, r in candidates if r]
            if candidates:
                headers, all_rows = max(candidates, key=lambda x: len(x[1]))
                all_headers = headers
        else:
            for table in tables:
                headers, rows = table_to_rows(table)
                if not rows:
                    continue
                for h in headers:
                    if h not in all_headers:
                        all_headers.append(h)
                all_rows.extend(rows)

        headers = all_headers

        if not all_rows:
            print(f"  no data rows found")
            return

    if not all_rows:
        print(f"  no data rows found")
        return

    out_path = OUT_DIR / f"{name}.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"  saved {len(all_rows)} rows → {out_path}")


def main() -> None:
    print(f"Output directory: {OUT_DIR.resolve()}\n")
    for name, path in CATEGORIES.items():
        try:
            scrape_category(name, path)
        except Exception as exc:
            print(f"  ERROR: {exc}")

    print("\nDone.")


if __name__ == "__main__":
    main()
