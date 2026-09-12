#!/usr/bin/env python3
"""Enrich catalog.json attribution from Commons metadata; localize remote files.

Preserves existing entries; fills artist/license/source when wiki_file is known
or when Wikipedia free pageimage can be resolved.
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
PORTRAITS = ROOT / "docs" / "media" / "portraits"
CATALOG = ROOT / "docs" / "media" / "catalog.json"
UA = "VerticalWorldAnthology/1.0 (catalog enrich; attribution)"


def api_get(url: str, retries: int = 4) -> dict:
    delay = 2.0
    last: Exception | None = None
    for _ in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = e
            if e.code not in (429, 500, 502, 503):
                raise
            ra = e.headers.get("Retry-After")
            wait = min(float(ra), 45) if ra and str(ra).replace(".", "", 1).isdigit() else delay
            time.sleep(wait)
            delay = min(delay * 1.6, 45)
        except Exception as e:
            last = e
            time.sleep(delay)
            delay = min(delay * 1.5, 45)
    raise last or RuntimeError("api_get failed")


def commons_imageinfo_batch(file_titles: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    cleaned = []
    for t in file_titles:
        if not t:
            continue
        if not t.startswith("File:"):
            t = "File:" + t
        cleaned.append(t)
    for i in range(0, len(cleaned), 40):
        chunk = cleaned[i : i + 40]
        q = urllib.parse.urlencode(
            {
                "action": "query",
                "titles": "|".join(chunk),
                "prop": "imageinfo",
                "iiprop": "url|extmetadata|user",
                "iiurlwidth": 900,
                "format": "json",
                "formatversion": "2",
            }
        )
        data = api_get(f"https://commons.wikimedia.org/w/api.php?{q}")
        for page in data.get("query", {}).get("pages") or []:
            if page.get("missing"):
                continue
            title = page.get("title") or ""
            infos = page.get("imageinfo") or []
            if infos:
                out[title] = infos[0]
                out[title.replace("File:", "")] = infos[0]
        time.sleep(0.4)
    return out


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


def strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


def artist_credit(meta: dict) -> str:
    ext = meta.get("extmetadata") or {}
    for key in ("Artist", "Credit", "Attribution"):
        val = (ext.get(key, {}) or {}).get("value")
        if val:
            return strip_html(val)[:300]
    return meta.get("user") or "Unknown"


def license_bits(meta: dict) -> tuple[str, str]:
    ext = meta.get("extmetadata") or {}
    lic = (ext.get("LicenseShortName", {}) or {}).get("value", "") or "free"
    url = (ext.get("LicenseUrl", {}) or {}).get("value", "") or ""
    return lic, url


def download(url: str, dest: Path) -> None:
    delay = 3.0
    last: Exception | None = None
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as resp:
                dest.write_bytes(resp.read())
                return
        except urllib.error.HTTPError as e:
            last = e
            if e.code != 429:
                raise
            wait = min(delay, 45)
            print(f"  rate-limited, sleep {wait:.0f}s")
            time.sleep(wait)
            delay = min(delay * 1.6, 45)
        except Exception as e:
            last = e
            time.sleep(delay)
    raise last or RuntimeError("download failed")


def needs_enrich(item: dict) -> bool:
    artist = (item.get("artist") or "").lower()
    if "see commons" in artist or "wikimedia contributor" in artist:
        return True
    if artist.startswith("wikipedia ("):
        return True
    if not item.get("license_url") and item.get("wiki_file"):
        return True
    if str(item.get("file", "")).startswith("http"):
        return True
    note = (item.get("note") or "").lower()
    if "pending" in note or "exact commons" in note:
        return True
    return False


def main() -> None:
    people = {p["id"]: p for p in json.loads(PEOPLE.read_text(encoding="utf-8"))}
    people_by_slug = {p["slug"]: p for p in people.values() if p.get("slug")}
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    PORTRAITS.mkdir(parents=True, exist_ok=True)

    # Only enrich from known wiki_file — do not invent new pageimages here
    # (pageimage may be a grave/map/equipment shot).
    titles = [c.get("wiki_file") or "" for c in catalog if c.get("wiki_file") and needs_enrich(c)]
    print(f"batch imageinfo for {len(titles)} files…")
    infos = commons_imageinfo_batch(titles)

    enriched = localized = 0
    for item in catalog:
        slug = item.get("slug") or ""
        # localize remote
        f = item.get("file") or ""
        if f.startswith("http"):
            ext = Path(urllib.parse.urlparse(f).path).suffix.lower() or ".jpg"
            if "?" in ext:
                ext = ".jpg"
            if len(ext) > 5:
                ext = ".jpg"
            dest_rel = f"media/portraits/{slug}{ext}"
            dest = ROOT / "docs" / dest_rel
            try:
                if not dest.exists():
                    print(f"download remote {slug}")
                    download(f, dest)
                    time.sleep(1.2)
                item["file"] = dest_rel
                localized += 1
            except Exception as e:
                print(f"localize fail {slug}: {e}")

        wf = item.get("wiki_file") or ""
        info = infos.get(wf) or infos.get("File:" + wf) if wf else None
        if info and needs_enrich(item):
            item["artist"] = artist_credit(info)
            item["credit"] = artist_credit(info)
            lic, lic_url = license_bits(info)
            item["license"] = lic
            item["license_short"] = lic
            item["license_url"] = lic_url
            item["source_url"] = info.get("descriptionurl") or item.get("source_url") or ""
            item["commons_url"] = info.get("descriptionurl") or item.get("commons_url") or ""
            item.pop("note", None)
            enriched += 1
            print(f"enriched {slug}: {lic} — {item['artist'][:50]}")

        # sync names from people_index
        person = people.get(item["id"]) or people_by_slug.get(slug)
        if person and person.get("names"):
            item["names"] = person["names"]

    catalog = sorted(catalog, key=lambda x: x.get("slug") or "")
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"done: enriched={enriched} localized={localized} catalog={len(catalog)}")


if __name__ == "__main__":
    main()
