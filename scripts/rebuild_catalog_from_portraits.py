#!/usr/bin/env python3
"""Rebuild catalog.json from already-downloaded portrait files + people_index."""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEOPLE = ROOT / "docs" / "media" / "people_index.json"
PORTRAITS = ROOT / "docs" / "media" / "portraits"
CATALOG = ROOT / "docs" / "media" / "catalog.json"
UA = "VerticalWorldAnthology/1.0 (catalog rebuild; attribution)"


def api_get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.loads(resp.read().decode("utf-8"))


def commons_imageinfo(file_title: str) -> dict | None:
    if not file_title.startswith("File:"):
        file_title = "File:" + file_title
    q = urllib.parse.urlencode(
        {
            "action": "query",
            "titles": file_title,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|user",
            "format": "json",
            "formatversion": "2",
        }
    )
    data = api_get(f"https://commons.wikimedia.org/w/api.php?{q}")
    pages = data.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return None
    infos = pages[0].get("imageinfo") or []
    return infos[0] if infos else None


def wiki_pageimage(lang: str, title: str) -> str | None:
    q = urllib.parse.urlencode(
        {
            "action": "query",
            "prop": "pageimages",
            "titles": urllib.parse.unquote(title.replace("_", " ")),
            "pilicense": "free",
            "format": "json",
            "formatversion": "2",
        }
    )
    data = api_get(f"https://{lang}.wikipedia.org/w/api.php?{q}")
    pages = data.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return None
    return pages[0].get("pageimage")


def artist_credit(meta: dict) -> str:
    ext = meta.get("extmetadata") or {}
    for key in ("Artist", "Credit", "Attribution"):
        val = (ext.get(key, {}) or {}).get("value")
        if val:
            return re.sub(r"<[^>]+>", "", val).strip()[:300]
    return meta.get("user") or "Unknown"


def license_bits(meta: dict) -> tuple[str, str]:
    ext = meta.get("extmetadata") or {}
    lic = (ext.get("LicenseShortName", {}) or {}).get("value", "") or "free"
    url = (ext.get("LicenseUrl", {}) or {}).get("value", "") or ""
    return lic, url


def main() -> None:
    people = {p.get("slug"): p for p in json.loads(PEOPLE.read_text(encoding="utf-8")) if p.get("slug")}
    existing = {i["id"]: i for i in json.loads(CATALOG.read_text(encoding="utf-8"))} if CATALOG.exists() else {}
    catalog = []
    files = sorted(PORTRAITS.glob("*"))
    print(f"portraits on disk: {len(files)}")
    for path in files:
        slug = path.stem
        person = people.get(slug)
        if not person:
            # try without case
            person = next((p for s, p in people.items() if s.lower() == slug.lower()), None)
        if not person:
            print("no person for", path.name)
            continue
        if person["id"] in existing and existing[person["id"]].get("file"):
            catalog.append(existing[person["id"]])
            continue
        titles = person.get("wiki_titles") or {}
        file_title = None
        lang_used = None
        for lang in ("en", "ru", "de", "fr", "it", "pl", "es", "ja"):
            if lang not in titles:
                continue
            try:
                file_title = wiki_pageimage(lang, titles[lang])
                if file_title:
                    lang_used = lang
                    break
            except Exception as e:
                print("wiki fail", slug, e)
                time.sleep(2)
        dest_rel = f"media/portraits/{path.name}"
        item = {
            "id": person["id"],
            "slug": slug,
            "names": person.get("names", {}),
            "file": dest_rel,
            "artist": "Wikipedia / Wikimedia Commons",
            "credit": "Wikipedia / Wikimedia Commons",
            "source_url": "",
            "commons_url": "",
            "license": "Free (Wikipedia pageimage filter)",
            "license_short": "free",
            "license_url": "",
            "wiki_file": file_title or "",
        }
        if file_title:
            try:
                info = commons_imageinfo(file_title)
                if info:
                    item["artist"] = artist_credit(info)
                    item["credit"] = artist_credit(info)
                    lic, lic_url = license_bits(info)
                    item["license"] = lic
                    item["license_short"] = lic
                    item["license_url"] = lic_url
                    item["source_url"] = info.get("descriptionurl") or ""
                    item["commons_url"] = info.get("descriptionurl") or ""
            except Exception as e:
                print("commons fail", slug, e)
                time.sleep(2)
        if not item["source_url"] and lang_used and lang_used in titles:
            item["source_url"] = f"https://{lang_used}.wikipedia.org/wiki/{titles[lang_used]}"
        catalog.append(item)
        print("catalogued", slug, item["license"])
        time.sleep(0.7)
        # incremental save
        CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", len(catalog), "entries")


if __name__ == "__main__":
    main()
