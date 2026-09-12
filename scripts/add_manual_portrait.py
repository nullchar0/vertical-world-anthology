#!/usr/bin/env python3
"""Register a manually obtained portrait (author permission / paid license / archive).

Usage:
  python3 scripts/add_manual_portrait.py \\
    --slug messner-rainhold \\
    --file ~/Downloads/messner.jpg \\
    --artist "Jane Doe" \\
    --source-url "https://example.com/photo/123" \\
    --license "Permission from author (non-exclusive web use)" \\
    --license-url "" \\
    --note "Email permission 2026-09-12"

The image is copied to docs/media/portraits/<slug>.<ext> and catalog.json is updated.
Slug must exist in docs/media/people_index.json (from a wiki/ext link in the anthology).
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEOPLE = ROOT / "docs" / "media" / "people_index.json"
PORTRAITS = ROOT / "docs" / "media" / "portraits"
CATALOG = ROOT / "docs" / "media" / "catalog.json"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--slug", required=True, help="Person slug from people_index.json")
    ap.add_argument("--file", required=True, help="Path to local image file")
    ap.add_argument("--artist", required=True, help="Author / rightsholder credit line")
    ap.add_argument("--source-url", required=True, help="Link to original or permission record")
    ap.add_argument("--license", required=True, help="License or permission summary")
    ap.add_argument("--license-url", default="", help="Optional license deed URL")
    ap.add_argument("--note", default="", help="Optional internal note (permission date, etc.)")
    args = ap.parse_args()

    people = {p["slug"]: p for p in json.loads(PEOPLE.read_text(encoding="utf-8"))}
    person = people.get(args.slug)
    if not person:
        raise SystemExit(
            f"Unknown slug {args.slug!r}. Check docs/media/people_index.json "
            f"(rebuild with scripts/build_people_index.py if the person is linked in content)."
        )

    src = Path(args.file).expanduser().resolve()
    if not src.is_file():
        raise SystemExit(f"File not found: {src}")

    ext = src.suffix.lower() or ".jpg"
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        raise SystemExit(f"Unsupported image type: {ext}")

    PORTRAITS.mkdir(parents=True, exist_ok=True)
    # remove other extensions for same slug
    for old in PORTRAITS.glob(args.slug + ".*"):
        if old.suffix.lower() != ext:
            old.unlink()

    dest = PORTRAITS / f"{args.slug}{ext}"
    shutil.copy2(src, dest)
    dest_rel = f"media/portraits/{dest.name}"

    catalog = json.loads(CATALOG.read_text(encoding="utf-8")) if CATALOG.exists() else []
    by_id = {c["id"]: c for c in catalog}
    item = {
        "id": person["id"],
        "slug": args.slug,
        "names": person.get("names", {}),
        "file": dest_rel,
        "artist": args.artist.strip()[:300],
        "credit": args.artist.strip()[:300],
        "source_url": args.source_url.strip(),
        "commons_url": "",
        "license": args.license.strip(),
        "license_short": args.license.strip()[:80],
        "license_url": args.license_url.strip(),
        "wiki_file": "",
        "found_via": "manual-permission",
    }
    if args.note.strip():
        item["note"] = args.note.strip()[:500]
    by_id[item["id"]] = item
    out = sorted(by_id.values(), key=lambda x: x.get("slug") or "")
    CATALOG.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK {args.slug} -> {dest_rel}")
    print("Commit docs/media/portraits/ and docs/media/catalog.json, then push to publish.")


if __name__ == "__main__":
    main()
