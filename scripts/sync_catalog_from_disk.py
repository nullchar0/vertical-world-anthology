#!/usr/bin/env python3
"""Rebuild catalog.json entries from portraits on disk + people_index.json (no network)."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEOPLE = ROOT / "docs" / "media" / "people_index.json"
PORTRAITS = ROOT / "docs" / "media" / "portraits"
CATALOG = ROOT / "docs" / "media" / "catalog.json"

def main() -> None:
    people = {p["slug"]: p for p in json.loads(PEOPLE.read_text(encoding="utf-8"))}
    catalog = []
    unmatched = []
    for path in sorted(PORTRAITS.glob("*")):
        person = people.get(path.stem)
        if not person:
            unmatched.append(path.name)
            continue
        titles = person.get("wiki_titles") or {}
        lang = next((l for l in ("en", "ru", "de", "fr", "it", "pl", "es", "ja") if l in titles), None)
        source = (
            f"https://{lang}.wikipedia.org/wiki/{titles[lang]}"
            if lang
            else (person.get("urls") or [""])[0]
        )
        catalog.append(
            {
                "id": person["id"],
                "slug": person["slug"],
                "names": person.get("names", {}),
                "file": f"media/portraits/{path.name}",
                "artist": "Wikimedia contributor (see source file page)",
                "credit": "Retrieved via Wikipedia free pageimage filter; see source for author & license details",
                "source_url": source,
                "commons_url": source,
                "license": "Free / open license (Wikipedia pilicense=free)",
                "license_short": "free",
                "license_url": "https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use",
                "wiki_file": "",
                "note": "Run scripts/rebuild_catalog_from_portraits.py to fill exact Commons artist/license.",
            }
        )
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"catalog={len(catalog)} unmatched={unmatched}")

if __name__ == "__main__":
    main()
