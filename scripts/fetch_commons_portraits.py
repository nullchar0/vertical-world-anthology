#!/usr/bin/env python3
"""Fetch freely licensed portraits from Wikipedia / Wikimedia Commons.

Writes:
  docs/media/catalog.json
  docs/media/portraits/<slug>.jpg|png|...

Only stores images when MediaWiki returns a usable license (or public domain).
Attribution fields are filled for on-site credit lines.
"""
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
OUT_DIR = ROOT / "docs" / "media" / "portraits"
CATALOG = ROOT / "docs" / "media" / "catalog.json"
UA = "VerticalWorldAnthology/1.0 (GitHub Pages educational anthology; portrait attribution)"

ALLOWED_LICENSE_HINTS = (
    "public domain",
    "cc0",
    "cc-zero",
    "cc by",
    "cc-by",
    "creative commons attribution",
    "gfdl",
    "copyrighted free use",
    "attribution",
)

DISALLOWED_HINTS = (
    "fair use",
    "non-free",
    "all rights reserved",
    "copyrighted",  # alone is weak; checked with care below
)


def api_get(url: str, retries: int = 8) -> dict:
    delay = 2.0
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code != 429:
                raise
            # honor Retry-After when present
            ra = e.headers.get("Retry-After")
            wait = float(ra) if ra and ra.isdigit() else delay
            print(f"  rate-limited, sleep {wait:.1f}s (attempt {attempt + 1}/{retries})")
            time.sleep(wait)
            delay = min(delay * 1.7, 90)
        except Exception as e:
            last_err = e
            time.sleep(delay)
            delay = min(delay * 1.5, 60)
    raise last_err or RuntimeError("api_get failed")


def wiki_api(lang: str, params: dict) -> dict:
    params = dict(params)
    params.setdefault("format", "json")
    params.setdefault("formatversion", "2")
    q = urllib.parse.urlencode(params)
    return api_get(f"https://{lang}.wikipedia.org/w/api.php?{q}")


def commons_api(params: dict) -> dict:
    params = dict(params)
    params.setdefault("format", "json")
    params.setdefault("formatversion", "2")
    q = urllib.parse.urlencode(params)
    return api_get(f"https://commons.wikimedia.org/w/api.php?{q}")


def pick_wiki_lang(person: dict) -> tuple[str, str] | None:
    titles = person.get("wiki_titles") or {}
    for lang in ("en", "ru", "de", "fr", "it", "pl", "es", "ja", "zh", "ko"):
        if lang in titles:
            return lang, titles[lang]
    return None


def page_image_title(lang: str, title: str) -> str | None:
    data = wiki_api(
        lang,
        {
            "action": "query",
            "prop": "pageimages",
            "titles": urllib.parse.unquote(title),
            "pithumbsize": 800,
            "pilicense": "free",
        },
    )
    pages = data.get("query", {}).get("pages", [])
    if not pages:
        return None
    page = pages[0]
    if page.get("missing"):
        return None
    # original file title preferred
    if "pageimage" in page:
        return page["pageimage"]
    thumb = page.get("thumbnail", {}).get("source")
    return None if not thumb else None


def imageinfo(file_title: str) -> dict | None:
    if not file_title.startswith("File:"):
        file_title = "File:" + file_title
    data = commons_api(
        {
            "action": "query",
            "titles": file_title,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|size|mime|user",
            "iiurlwidth": 800,
        }
    )
    pages = data.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        # try wikipedia local file via en
        return None
    infos = pages[0].get("imageinfo") or []
    return infos[0] if infos else None


def license_ok(meta: dict) -> tuple[bool, str, str]:
    ext = meta.get("extmetadata") or {}
    license_short = (ext.get("LicenseShortName", {}) or {}).get("value", "") or ""
    license_url = (ext.get("LicenseUrl", {}) or {}).get("value", "") or ""
    usage = (ext.get("UsageTerms", {}) or {}).get("value", "") or ""
    restrictions = (ext.get("Restrictions", {}) or {}).get("value", "") or ""
    blob = f"{license_short} {usage} {restrictions}".lower()
    if "fair use" in blob or "non-free" in blob:
        return False, license_short, license_url
    if any(h in blob for h in ALLOWED_LICENSE_HINTS):
        return True, license_short or usage or "free", license_url
    # PD marks
    if "pd-" in blob or license_short.upper().startswith("PD"):
        return True, license_short or "Public domain", license_url
    return False, license_short, license_url


def artist_credit(meta: dict) -> str:
    ext = meta.get("extmetadata") or {}
    for key in ("Artist", "Credit", "Attribution"):
        val = (ext.get(key, {}) or {}).get("value")
        if val:
            # strip simple html
            return re.sub(r"<[^>]+>", "", val).strip()[:300]
    return meta.get("user") or "Unknown"


def download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        dest.write_bytes(resp.read())


def main() -> None:
    people = json.loads(PEOPLE.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    existing = {}
    if CATALOG.exists():
        for item in json.loads(CATALOG.read_text(encoding="utf-8")):
            existing[item["id"]] = item

    catalog = []
    ok = skip = fail = 0
    for i, person in enumerate(people, 1):
        pid = person["id"]
        slug = person.get("slug") or f"person-{i}"
        if pid in existing and (ROOT / "docs" / existing[pid].get("file", "")).exists():
            catalog.append(existing[pid])
            ok += 1
            continue

        picked = pick_wiki_lang(person)
        if not picked:
            skip += 1
            continue
        lang, title = picked
        try:
            data = wiki_api(
                lang,
                {
                    "action": "query",
                    "prop": "pageimages",
                    "titles": urllib.parse.unquote(title.replace("_", " ")),
                    "pithumbsize": 800,
                    "pilicense": "free",
                },
            )
            pages = data.get("query", {}).get("pages", [])
            if not pages or pages[0].get("missing") or "pageimage" not in pages[0]:
                skip += 1
                time.sleep(0.35)
                continue
            file_title = pages[0]["pageimage"]
            info = imageinfo(file_title)
            if not info:
                # local wiki file fallback: use thumbnail url only if free flag already applied
                thumb = pages[0].get("thumbnail", {}).get("source")
                if not thumb:
                    skip += 1
                    time.sleep(0.35)
                    continue
                # Without commons metadata we still record Wikipedia pageimage under free filter
                ext = Path(urllib.parse.urlparse(thumb).path).suffix or ".jpg"
                dest_rel = f"media/portraits/{slug}{ext}"
                dest = ROOT / "docs" / dest_rel
                if not dest.exists():
                    download(thumb, dest)
                item = {
                    "id": pid,
                    "slug": slug,
                    "names": person.get("names", {}),
                    "file": dest_rel,
                    "artist": f"Wikipedia ({lang})",
                    "credit": f"Page image from {lang}.wikipedia.org",
                    "source_url": f"https://{lang}.wikipedia.org/wiki/{title}",
                    "commons_url": f"https://{lang}.wikipedia.org/wiki/File:{urllib.parse.quote(file_title)}",
                    "license": "Free (Wikipedia pageimage filter)",
                    "license_short": "free",
                    "license_url": "",
                    "wiki_file": file_title,
                }
                catalog.append(item)
                ok += 1
                CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
                time.sleep(0.6)
                continue

            good, lic, lic_url = license_ok(info)
            if not good:
                skip += 1
                time.sleep(0.35)
                continue
            url = info.get("thumburl") or info.get("url")
            if not url:
                skip += 1
                continue
            ext = Path(urllib.parse.urlparse(url).path).suffix or ".jpg"
            if len(ext) > 5:
                ext = ".jpg"
            dest_rel = f"media/portraits/{slug}{ext}"
            dest = ROOT / "docs" / dest_rel
            if not dest.exists():
                download(url, dest)
            item = {
                "id": pid,
                "slug": slug,
                "names": person.get("names", {}),
                "file": dest_rel,
                "artist": artist_credit(info),
                "credit": artist_credit(info),
                "source_url": info.get("descriptionurl")
                or f"https://commons.wikimedia.org/wiki/File:{urllib.parse.quote(file_title)}",
                "commons_url": info.get("descriptionurl"),
                "license": lic,
                "license_short": lic,
                "license_url": lic_url,
                "wiki_file": file_title,
            }
            catalog.append(item)
            ok += 1
            print(f"[{i}/{len(people)}] OK {slug} ({lic})")
            CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            fail += 1
            print(f"[{i}/{len(people)}] FAIL {slug}: {e}")
            time.sleep(2.0)
        time.sleep(0.55)

    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"done: ok={ok} skip={skip} fail={fail} catalog={len(catalog)}")


if __name__ == "__main__":
    main()
