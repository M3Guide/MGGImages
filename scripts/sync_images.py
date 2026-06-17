"""
Syncs mutant images from the kobojo CDN into this repo, driven by a
published Google Sheet CSV with columns: ID, Gene 1, Category, Skins.

- Larva image:        larva_{ID}.png                 -> larva/{Gene1}/{ID}.png
- Base specimen icon: specimen_{ID}.png               -> icons/{Gene1}/{ID}.png
- Skin icons:          specimen_{ID}_{skin}.png        -> icons/{Gene1}/{ID}_{skin}.png

Skin list per row = (Skins column, split on "/") UNION extra tiers based on Category:
  - Category in {Common, Legendary, PvP, Heroic, Secret} -> + {bronze, silver, gold, platinum}
  - Category == Zodiac                                   -> + {silver}

Existing files are skipped unless FORCE_REDOWNLOAD=true (set by the
workflow's manual "force" input), so daily runs only fetch what's new.
"""

import csv
import io
import os

import requests

# --- Configuration -----------------------------------------------------
# Paste your "Publish to web" CSV link here:
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQh2Z4QbBx5VxQgAwXOueCe3TKK9abQQ-XWVyf5tCGKg3pIxnjhJO6buOVhOO8pCuzYmwvr5dppYTgn/pub?output=csv"

THUMB_BASE = "https://s-ak.kobojo.com/mutants/assets/thumbnails"
LARVA_BASE = "https://s-ak.kobojo.com/mutants/assets/larvas"

ICONS_DIR = "icons"
LARVA_DIR = "larva"

STARRED_CATEGORIES = {"Common", "Legendary", "PvP", "Heroic", "Secret"}
STARRED_SKINS = {"bronze", "silver", "gold", "platinum"}
ZODIAC_CATEGORY = "Zodiac"
ZODIAC_SKINS = {"silver"}

FORCE = os.environ.get("FORCE_REDOWNLOAD", "false").strip().lower() == "true"

def fetch_csv_rows(url):
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    resp.encoding = resp.encoding or "utf-8"
    reader = csv.DictReader(io.StringIO(resp.text))
    return list(reader)


def download(url, dest_path):
    if os.path.exists(dest_path) and not FORCE:
        return False
    try:
        r = requests.get(url, timeout=30)
    except requests.RequestException as e:
        print(f"  [error] {url}: {e}")
        return False

    if r.status_code != 200 or not r.content:
        print(f"  [skip] not found ({r.status_code}): {url}")
        return False
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, "wb") as f:
        f.write(r.content)
    print(f"  [saved] {dest_path}")
    return True


def build_skin_set(raw_skins, category):
    skins = set()
    if raw_skins:
        for s in raw_skins.split("/"):
            s = s.strip()
            if s:
                skins.add(s)

    if category in STARRED_CATEGORIES:
        skins |= STARRED_SKINS
    elif category == ZODIAC_CATEGORY:
        skins |= ZODIAC_SKINS

    return skins


def main():
    rows = fetch_csv_rows(CSV_URL)
    print(f"Loaded {len(rows)} rows from sheet.")
    changed = 0
    for row in rows:
        mutant_id = (row.get("ID") or "").strip()
        gene1 = (row.get("Gene 1") or "").strip()
        category = (row.get("Category") or "").strip()
        raw_skins = (row.get("Skins") or "").strip()

        if not mutant_id or not gene1:
            continue

        print(f"Processing ID={mutant_id} Gene1={gene1} Category={category}")

        # Larva image
        larva_url = f"{LARVA_BASE}/larva_{mutant_id}.png"
        larva_dest = f"{LARVA_DIR}/{gene1}/{mutant_id}.png"
        if download(larva_url, larva_dest):
            changed += 1

        # Base specimen icon (always fetched first)
        base_url = f"{THUMB_BASE}/specimen_{mutant_id}.png"
        base_dest = f"{ICONS_DIR}/{gene1}/{mutant_id}.png"
        if download(base_url, base_dest):
            changed += 1

        # Skin icons
        for skin in sorted(build_skin_set(raw_skins, category)):
            skin_url = f"{THUMB_BASE}/specimen_{mutant_id}_{skin}.png"
            skin_dest = f"{ICONS_DIR}/{gene1}/{mutant_id}_{skin}.png"
            if download(skin_url, skin_dest):
                changed += 1

    print(f"Done. {changed} file(s) newly downloaded.")


if __name__ == "__main__":
    main()