#!/usr/bin/env python3
"""Find freely licensed portraits for people missing Wikipedia pageimages.

Primary source: Wikimedia Commons file search by person name.
Optional fallback: Openverse (CC0 / PD / BY / BY-SA only).

Writes/updates:
  docs/media/catalog.json
  docs/media/portraits/<slug>.*
"""
from __future__ import annotations

import argparse
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

SKIP_SLUGS = {
    "stolbisty",
    "1936-eiger-north-face-climbing-disaster",
}

ALLOWED_LICENSE_HINTS = (
    "public domain",
    "cc0",
    "cc-zero",
    "cc by",
    "cc-by",
    "creative commons attribution",
    "gfdl",
    "copyrighted free use",
)

# Prefer true free reuse; skip NC / ND for this anthology site.
DISALLOWED_LICENSE_HINTS = (
    "fair use",
    "non-free",
    "all rights reserved",
    "cc by-nc",
    "cc-by-nc",
    "cc by-nd",
    "cc-by-nd",
    "noncommercial",
    "non-commercial",
)

BAD_TITLE_BITS = (
    "plaque",
    "graffiti",
    "memorial",
    "statue",
    "bust",
    "map",
    "logo",
    "coat of arms",
    "signature",
    "autograph",
    "grave",
    "tomb",
    "djvu",
    "svg",
    "pdf",
    "stamp",
    "coin",
    "museum exterior",
    "practice wall",
    "region based",
    "straße",
    "strasse",
    "street",
    "seen from",
    "eispickel",
    "ice axe",
    "seil und",
    "rope",
    "pickel",
    "equipment",
    "gear",
    "and other",
    "en andere",
    "members of",
    "expedition members",
    "team photo",
    "preis",
    "prize",
    "award",
    "verleihung",
    "ceremony",
    "hotel",
    "inn and",
    "brücke",
    "bridge",
    "karabiner",
    "carabiner",
    "felshaken",
    "piton",
    "haken",
    "mmm corones",
    "cimetière",
    "cimetiere",
    "cemetery",
    "grab ",
    "grabmal",
    "rue ",
    "parc ",
    "park ",
    "square",
    "plaza",
)

NAME_STOPWORDS = {
    "the",
    "von",
    "van",
    "de",
    "da",
    "del",
    "della",
    "di",
    "la",
    "le",
    "der",
    "den",
    "of",
    "and",
    "jr",
    "sr",
    "climber",
    "mountaineer",
    "alpinist",
    "bergsteiger",
    "sherpa",
    "colorized",
    "portrait",
    "official",
}


def api_get(url: str, retries: int = 3, timeout: int = 25) -> dict:
    delay = 1.5
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code not in (429, 500, 502, 503):
                raise
            ra = e.headers.get("Retry-After")
            wait = float(ra) if ra and str(ra).isdigit() else delay
            time.sleep(wait)
            delay = min(delay * 1.7, 60)
        except Exception as e:
            last_err = e
            time.sleep(delay)
            delay = min(delay * 1.5, 45)
    raise last_err or RuntimeError("api_get failed")


def commons_api(params: dict) -> dict:
    params = dict(params)
    params.setdefault("format", "json")
    params.setdefault("formatversion", "2")
    q = urllib.parse.urlencode(params)
    return api_get(f"https://commons.wikimedia.org/w/api.php?{q}")


def wiki_api(lang: str, params: dict) -> dict:
    params = dict(params)
    params.setdefault("format", "json")
    params.setdefault("formatversion", "2")
    q = urllib.parse.urlencode(params)
    return api_get(f"https://{lang}.wikipedia.org/w/api.php?{q}")


def wikidata_p18(person: dict) -> str | None:
    """Return Commons File: title from Wikidata image (P18), if present."""
    titles = person.get("wiki_titles") or {}
    for lang in ("en", "ru", "de", "fr", "it", "pl", "es", "ja", "zh"):
        if lang not in titles:
            continue
        title = urllib.parse.unquote(titles[lang].replace("_", " "))
        try:
            data = wiki_api(
                lang,
                {
                    "action": "query",
                    "prop": "pageprops",
                    "ppprop": "wikibase_item",
                    "titles": title,
                },
            )
            pages = data.get("query", {}).get("pages") or []
            if not pages or pages[0].get("missing"):
                continue
            qid = (pages[0].get("pageprops") or {}).get("wikibase_item")
            if not qid:
                continue
            wd = api_get(
                "https://www.wikidata.org/w/api.php?"
                + urllib.parse.urlencode(
                    {
                        "action": "wbgetentities",
                        "ids": qid,
                        "props": "claims",
                        "format": "json",
                    }
                )
            )
            claims = (
                wd.get("entities", {})
                .get(qid, {})
                .get("claims", {})
                .get("P18")
            )
            if not claims:
                continue
            mainsnak = claims[0].get("mainsnak") or {}
            datavalue = mainsnak.get("datavalue") or {}
            val = datavalue.get("value")
            if isinstance(val, str) and val:
                return val if val.startswith("File:") else f"File:{val}"
        except Exception:
            continue
        time.sleep(0.2)
    return None


def strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


def display_names(person: dict) -> list[str]:
    names = person.get("names") or {}
    out: list[str] = []
    # Prefer full wiki titles first (include surname), then display names
    for lang, title in (person.get("wiki_titles") or {}).items():
        t = urllib.parse.unquote(title.replace("_", " "))
        t = re.sub(r"\s*\([^)]*\)\s*", " ", t).strip()
        t = t.replace(",", " ")
        t = re.sub(r"\s+", " ", t)
        if t and t not in out:
            out.append(t)
    for key in ("en", "ru", "de", "fr", "it", "pl", "es", "ja", "zh"):
        val = names.get(key)
        if val:
            cleaned = re.sub(r"\s*\([^)]*\)\s*", " ", val).strip()
            cleaned = cleaned.replace(",", " ")
            cleaned = re.sub(r"\s+", " ", cleaned)
            if cleaned and cleaned not in out:
                out.append(cleaned)
    return out


def name_tokens(name: str) -> list[str]:
    parts = re.findall(r"[A-Za-zА-Яа-яЁёÄÖÜäöüßČĆŠŽčćšžĐđĀāĒēĪīŌōŪūÑñ'-]+", name)
    tokens = []
    for p in parts:
        low = p.lower().strip("-'")
        if len(low) < 3 or low in NAME_STOPWORDS:
            continue
        tokens.append(low)
    return tokens


def file_stem(file_title: str) -> str:
    t = file_title
    if t.startswith("File:"):
        t = t[5:]
    return Path(t).stem.lower()


def title_matches_name(file_title: str, names: list[str]) -> bool:
    blob = file_title.lower()
    stem = file_stem(file_title)
    if any(b in blob for b in BAD_TITLE_BITS):
        return False
    if not re.search(r"\.(jpe?g|png|webp)\b", blob):
        return False
    # reject route diagrams / topo maps
    if any(x in stem for x in ("route", "nordwand", "topo", "map", "diagram")):
        return False
    for name in names:
        toks = name_tokens(name)
        if len(toks) < 2:
            if len(toks) == 1 and toks[0] in stem and len(stem) < len(toks[0]) + 18:
                return True
            continue
        stem_space = re.sub(r"[_\-.,]+", " ", stem)
        stem_compact = re.sub(r"[^a-zа-яё0-9]+", "", stem_space)
        phrase = " ".join(toks)
        phrase_rev = " ".join(reversed(toks))
        phrase_compact = "".join(toks)
        phrase_rev_c = "".join(reversed(toks))
        # Require contiguous full name (or reversed surname-firstname)
        if (
            phrase in stem_space
            or phrase_rev in stem_space
            or phrase_compact in stem_compact
            or phrase_rev_c in stem_compact
        ):
            return True
    return False


def license_ok(meta: dict) -> tuple[bool, str, str]:
    ext = meta.get("extmetadata") or {}
    license_short = (ext.get("LicenseShortName", {}) or {}).get("value", "") or ""
    license_url = (ext.get("LicenseUrl", {}) or {}).get("value", "") or ""
    usage = (ext.get("UsageTerms", {}) or {}).get("value", "") or ""
    restrictions = (ext.get("Restrictions", {}) or {}).get("value", "") or ""
    blob = f"{license_short} {usage} {restrictions}".lower()
    if any(h in blob for h in DISALLOWED_LICENSE_HINTS):
        return False, license_short, license_url
    if any(h in blob for h in ALLOWED_LICENSE_HINTS):
        return True, license_short or usage or "free", license_url
    if "pd-" in blob or license_short.upper().startswith("PD"):
        return True, license_short or "Public domain", license_url
    return False, license_short, license_url


def artist_credit(meta: dict) -> str:
    ext = meta.get("extmetadata") or {}
    for key in ("Artist", "Credit", "Attribution"):
        val = (ext.get(key, {}) or {}).get("value")
        if val:
            return strip_html(val)[:300]
    return meta.get("user") or "Unknown"


def imageinfo(file_title: str) -> dict | None:
    if not file_title.startswith("File:"):
        file_title = "File:" + file_title
    data = commons_api(
        {
            "action": "query",
            "titles": file_title,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|size|mime|user",
            "iiurlwidth": 900,
        }
    )
    pages = data.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return None
    infos = pages[0].get("imageinfo") or []
    return infos[0] if infos else None


def commons_search(query: str, limit: int = 12) -> list[str]:
    data = commons_api(
        {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srnamespace": 6,
            "srlimit": limit,
        }
    )
    return [hit["title"] for hit in data.get("query", {}).get("search", [])]


def openverse_search(query: str, limit: int = 5) -> list[dict]:
    url = "https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(
        {
            "q": query,
            "license": "cc0,pdm,by,by-sa",
            "page_size": limit,
            "category": "photograph",
        }
    )
    try:
        data = api_get(url, retries=2, timeout=18)
    except Exception:
        return []
    return data.get("results") or []


def score_title(title: str, names: list[str]) -> int:
    low = title.lower()
    stem = file_stem(title)
    stem_space = re.sub(r"[_\-.,]+", " ", stem)
    score = 0
    if "portrait" in low:
        score += 12
    if re.search(r"\b(19\d{2}|20\d{2})\b", low):
        score += 2
    for name in names:
        toks = name_tokens(name)
        if not toks:
            continue
        phrase = " ".join(toks)
        if phrase in stem_space:
            score += 20
        score += sum(4 for t in toks if t in stem_space)
        # bonus if filename starts with the person name
        if stem_space.startswith(toks[0]) or stem_space.startswith(phrase):
            score += 6
    if any(b in low for b in ("cropped", "detail")):
        score += 1
    if any(b in low for b in BAD_TITLE_BITS):
        score -= 40
    # penalize long non-portrait captions
    extras = [w for w in re.findall(r"[a-zа-яё]{5,}", stem_space)]
    if len(extras) > 6:
        score -= 8
    return score


def looks_like_person_photo(info: dict, names: list[str]) -> bool:
    """Reject maps/objects when metadata clearly isn't a person portrait."""
    ext = info.get("extmetadata") or {}
    categories = strip_html((ext.get("Categories", {}) or {}).get("value", "")).lower()
    obj = strip_html((ext.get("ObjectName", {}) or {}).get("value", "")).lower()
    desc = strip_html((ext.get("ImageDescription", {}) or {}).get("value", "")).lower()
    blob = f"{categories} {obj} {desc}"
    if any(x in blob for x in ("street", "straße", "building", "map of", "floor plan")):
        # allow if description still centers on the person
        if not any(all(t in blob for t in name_tokens(n)[:2]) for n in names if len(name_tokens(n)) >= 2):
            return False
    if "people" in categories or "portrait" in blob or "alpinist" in blob or "climber" in blob:
        return True
    # dimension heuristic: very wide panoramas are rarely portraits
    w = info.get("width") or 0
    h = info.get("height") or 0
    if w and h and w / max(h, 1) > 2.4:
        return False
    return True


def commons_category_files(name: str, limit: int = 20) -> list[str]:
    # Try common category title patterns
    titles = []
    for cat in (name, f"{name} (alpinist)", f"{name} (climber)", f"{name} (mountaineer)"):
        data = commons_api(
            {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": f"Category:{cat}",
                "cmtype": "file",
                "cmlimit": limit,
            }
        )
        members = data.get("query", {}).get("categorymembers") or []
        if members:
            titles.extend(m["title"] for m in members)
            break
    return titles


def pick_wiki_pageimage(person: dict) -> tuple[str, dict] | None:
    titles = person.get("wiki_titles") or {}
    for lang in ("en", "ru", "de", "fr", "it", "pl", "es", "ja", "zh"):
        if lang not in titles:
            continue
        title = urllib.parse.unquote(titles[lang].replace("_", " "))
        try:
            data = wiki_api(
                lang,
                {
                    "action": "query",
                    "prop": "pageimages",
                    "titles": title,
                    "pithumbsize": 900,
                    "pilicense": "free",
                },
            )
            pages = data.get("query", {}).get("pages") or []
            if not pages or pages[0].get("missing") or "pageimage" not in pages[0]:
                continue
            file_title = pages[0]["pageimage"]
            if not file_title.startswith("File:"):
                file_title = "File:" + file_title
            info = imageinfo(file_title)
            if not info:
                # local file on that wiki — use thumbnail if present
                thumb = (pages[0].get("thumbnail") or {}).get("source")
                if not thumb:
                    continue
                fake = {
                    "thumburl": thumb,
                    "url": thumb,
                    "descriptionurl": f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
                    "user": f"Wikipedia ({lang})",
                    "extmetadata": {
                        "LicenseShortName": {"value": "Free (Wikipedia pageimage)"},
                        "Artist": {"value": f"Wikipedia ({lang})"},
                    },
                }
                return file_title, fake
            good, _, _ = license_ok(info)
            if good:
                return file_title, info
        except Exception:
            continue
        time.sleep(0.15)
    return None


def pick_wikidata_image(person: dict) -> tuple[str, dict] | None:
    file_title = wikidata_p18(person)
    if not file_title:
        return None
    info = imageinfo(file_title)
    if not info:
        return None
    good, _, _ = license_ok(info)
    if not good:
        return None
    url = info.get("thumburl") or info.get("url")
    if not url:
        return None
    return file_title, info


def pick_commons_candidate(names: list[str]) -> tuple[str, dict] | None:
    seen: set[str] = set()
    candidates: list[tuple[int, str]] = []

    # Tight filename search only (categories often mix equipment / memorials)
    queries: list[str] = []
    for name in names[:2]:
        queries.append(f'intitle:"{name}"')
        queries.append(f'"{name}" portrait')
    for q in queries:
        try:
            for title in commons_search(q, limit=10):
                if title in seen:
                    continue
                seen.add(title)
                if not title_matches_name(title, names):
                    continue
                candidates.append((score_title(title, names), title))
        except Exception:
            continue
        time.sleep(0.18)

    candidates.sort(reverse=True)
    for _score, title in candidates[:8]:
        info = imageinfo(title)
        time.sleep(0.15)
        if not info:
            continue
        good, lic, _ = license_ok(info)
        if not good:
            continue
        mime = (info.get("mime") or "").lower()
        if mime and not mime.startswith("image/"):
            continue
        if not looks_like_person_photo(info, names):
            continue
        url = info.get("thumburl") or info.get("url")
        if not url:
            continue
        return title, info
    return None


def pick_openverse_candidate(names: list[str]) -> dict | None:
    for name in names[:3]:
        for q in (name, f"{name} climber", f"{name} mountaineer"):
            results = openverse_search(q)
            time.sleep(0.35)
            for item in results:
                title = item.get("title") or ""
                landing = item.get("foreign_landing_url") or ""
                blob = f"{title} {landing}".lower()
                if any(b in blob for b in BAD_TITLE_BITS):
                    continue
                # require name tokens in title or landing
                toks = name_tokens(name)
                if len(toks) >= 2 and not (toks[0] in blob and toks[-1] in blob):
                    continue
                if len(toks) == 1 and toks[0] not in blob:
                    continue
                lic = (item.get("license") or "").lower()
                if lic not in {"cc0", "pdm", "by", "by-sa"}:
                    continue
                if not item.get("url"):
                    continue
                return item
    return None


def catalog_item_from_commons(person: dict, file_title: str, info: dict) -> dict:
    slug = person["slug"]
    url = info.get("thumburl") or info.get("url")
    ext = Path(urllib.parse.urlparse(url).path).suffix.lower() or ".jpg"
    if len(ext) > 5:
        ext = ".jpg"
    dest_rel = f"media/portraits/{slug}{ext}"
    good, lic, lic_url = license_ok(info)
    artist = artist_credit(info)
    return {
        "id": person["id"],
        "slug": slug,
        "names": person.get("names", {}),
        "file": dest_rel,
        "artist": artist,
        "credit": artist,
        "source_url": info.get("descriptionurl")
        or f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(file_title)}",
        "commons_url": info.get("descriptionurl"),
        "license": lic,
        "license_short": lic,
        "license_url": lic_url,
        "wiki_file": file_title.replace("File:", ""),
        "found_via": "commons-search",
    }


def catalog_item_from_openverse(person: dict, item: dict) -> dict:
    slug = person["slug"]
    url = item["url"]
    ext = Path(urllib.parse.urlparse(url).path).suffix.lower() or ".jpg"
    if "?" in ext:
        ext = ext.split("?", 1)[0]
    if len(ext) > 5 or ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        ext = ".jpg"
    dest_rel = f"media/portraits/{slug}{ext}"
    creator = item.get("creator") or item.get("attribution") or "Unknown"
    lic = item.get("license") or ""
    lic_ver = item.get("license_version") or ""
    lic_label = f"CC {lic.upper()} {lic_ver}".strip() if lic not in {"pdm", "cc0"} else (
        "CC0" if lic == "cc0" else "Public Domain Mark"
    )
    return {
        "id": person["id"],
        "slug": slug,
        "names": person.get("names", {}),
        "file": dest_rel,
        "artist": creator[:300],
        "credit": (item.get("attribution") or creator)[:300],
        "source_url": item.get("foreign_landing_url") or item.get("url"),
        "commons_url": item.get("foreign_landing_url"),
        "license": lic_label,
        "license_short": lic,
        "license_url": item.get("license_url") or "",
        "wiki_file": "",
        "found_via": f"openverse:{item.get('source') or 'unknown'}",
        "openverse_id": item.get("id"),
    }


def has_usable_portrait(item: dict | None) -> bool:
    if not item:
        return False
    f = item.get("file") or ""
    if f.startswith("http://") or f.startswith("https://"):
        return True
    return (ROOT / "docs" / f).exists()


def is_bad_portrait_title(file_title: str) -> bool:
    low = (file_title or "").lower()
    if any(b in low for b in BAD_TITLE_BITS):
        return True
    if any(x in low for x in ("route", "nordwand", "topo", "diagram", "epitaph", "cimet")):
        return True
    return False


def commit_portrait(person: dict, file_title: str, info: dict, via: str, *, dry_run: bool, allow_remote: bool) -> dict:
    if is_bad_portrait_title(file_title):
        raise ValueError(f"rejected non-portrait file: {file_title}")
    item = catalog_item_from_commons(person, file_title, info)
    item["found_via"] = via
    url = info.get("thumburl") or info.get("url")
    dest = ROOT / "docs" / item["file"]
    if dry_run:
        return item
    if dest.exists():
        return item
    try:
        # Fail fast when remote fallback is allowed
        max_attempts = 2 if allow_remote else 8
        download(url, dest, max_attempts=max_attempts)
        time.sleep(1.0)
        return item
    except Exception as e:
        if allow_remote and url:
            item["file"] = url
            item["note"] = f"Remote Wikimedia URL (local download failed: {type(e).__name__})"
            print(f"    remote URL for {person['slug']}")
            return item
        raise


def download(url: str, dest: Path, max_attempts: int = 8) -> None:
    delay = 3.0
    last_err: Exception | None = None
    for attempt in range(max_attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as resp:
                dest.write_bytes(resp.read())
                return
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code != 429:
                raise
            ra = e.headers.get("Retry-After")
            wait = delay
            if ra and str(ra).replace(".", "", 1).isdigit():
                wait = min(float(ra), 45.0)
            print(f"    download rate-limited, sleep {wait:.1f}s (attempt {attempt+1})")
            time.sleep(wait)
            delay = min(delay * 1.6, 45)
        except Exception as e:
            last_err = e
            time.sleep(delay)
            delay = min(delay * 1.5, 45)
    raise last_err or RuntimeError("download failed")


def load_catalog() -> list[dict]:
    if not CATALOG.exists():
        return []
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def save_catalog(items: list[dict]) -> None:
    items = sorted(items, key=lambda x: (x.get("slug") or x.get("id") or ""))
    CATALOG.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def batch_imageinfo(file_titles: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    cleaned = []
    for t in file_titles:
        if not t.startswith("File:"):
            t = "File:" + t
        cleaned.append(t)
    for i in range(0, len(cleaned), 40):
        chunk = cleaned[i : i + 40]
        data = commons_api(
            {
                "action": "query",
                "titles": "|".join(chunk),
                "prop": "imageinfo",
                "iiprop": "url|extmetadata|size|mime|user",
                "iiurlwidth": 900,
            }
        )
        for page in data.get("query", {}).get("pages") or []:
            if page.get("missing"):
                continue
            title = page.get("title") or ""
            infos = page.get("imageinfo") or []
            if infos:
                out[title] = infos[0]
                out[title.replace("File:", "")] = infos[0]
        time.sleep(0.25)
    return out


def batch_pageimages(lang: str, title_to_person: dict[str, dict]) -> dict[str, tuple[str, dict]]:
    """Map person id -> (file_title, info) for free pageimages."""
    found: dict[str, tuple[str, dict]] = {}
    titles = list({t for t in title_to_person if t})
    pending: list[tuple[dict, str, dict]] = []
    for i in range(0, len(titles), 40):
        chunk = titles[i : i + 40]
        print(f"  pageimage query {lang} {i+1}-{i+len(chunk)}/{len(titles)}")
        data = wiki_api(
            lang,
            {
                "action": "query",
                "prop": "pageimages",
                "titles": "|".join(chunk),
                "pithumbsize": 900,
                "pilicense": "free",
            },
        )
        norm = {n["to"]: n["from"] for n in data.get("query", {}).get("normalized") or []}
        redirects = {r["to"]: r["from"] for r in data.get("query", {}).get("redirects") or []}
        for page in data.get("query", {}).get("pages") or []:
            if page.get("missing") or "pageimage" not in page:
                continue
            title = page.get("title") or ""
            original = redirects.get(title, title)
            original = norm.get(original, original)
            person = title_to_person.get(original) or title_to_person.get(title)
            if not person:
                key = title.replace(" ", "_")
                for t, p in title_to_person.items():
                    if t.replace("_", " ") == title or t == key:
                        person = p
                        break
            if not person:
                continue
            file_title = page["pageimage"]
            if not file_title.startswith("File:"):
                file_title = "File:" + file_title
            pending.append((person, file_title, page))
        time.sleep(0.25)

    print(f"  pageimage hits={len(pending)}; batch imageinfo…")
    infos = batch_imageinfo([ft for _, ft, _ in pending]) if pending else {}
    for person, file_title, page in pending:
        info = infos.get(file_title) or infos.get(file_title.replace("File:", ""))
        if info and license_ok(info)[0]:
            found[person["id"]] = (file_title, info)
            continue
        thumb = (page.get("thumbnail") or {}).get("source")
        if thumb:
            fake = {
                "thumburl": thumb,
                "url": thumb,
                "descriptionurl": f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote((page.get('title') or '').replace(' ', '_'))}",
                "user": f"Wikipedia ({lang})",
                "extmetadata": {
                    "LicenseShortName": {"value": "Free (Wikipedia pageimage)"},
                    "Artist": {"value": f"Wikipedia ({lang})"},
                },
            }
            found[person["id"]] = (file_title, fake)
    return found


def batch_wikidata_p18(people: list[dict]) -> dict[str, str]:
    """Return person_id -> File:title via Wikipedia sitelinks SPARQL."""
    articles = []
    id_by_article: dict[str, str] = {}
    for person in people:
        for lang, title in (person.get("wiki_titles") or {}).items():
            t = urllib.parse.unquote(title).replace(" ", "_")
            url = f"https://{lang}.wikipedia.org/wiki/{t}"
            articles.append(url)
            id_by_article[url] = person["id"]
            # also encoded form
            enc = f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(t)}"
            id_by_article[enc] = person["id"]
    if not articles:
        return {}
    out: dict[str, str] = {}
    for i in range(0, len(articles), 60):
        chunk = articles[i : i + 60]
        values = " ".join(f"<{u}>" for u in chunk)
        sparql = f"""
SELECT ?article ?image WHERE {{
  VALUES ?article {{ {values} }}
  ?article schema:about ?item .
  ?item wdt:P18 ?image .
}}
"""
        url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode(
            {"query": sparql, "format": "json"}
        )
        try:
            data = api_get(url, retries=3, timeout=60)
        except Exception as e:
            print(f"  SPARQL batch failed: {e}")
            continue
        for row in data.get("results", {}).get("bindings", []):
            article = row.get("article", {}).get("value", "")
            image = row.get("image", {}).get("value", "")
            pid = id_by_article.get(article)
            if not pid or not image:
                continue
            # image is like http://commons.wikimedia.org/wiki/Special:FilePath/Foo.jpg
            fname = urllib.parse.unquote(image.split("/")[-1])
            out[pid] = fname if fname.startswith("File:") else f"File:{fname}"
        time.sleep(0.5)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="Max missing people to process")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-openverse", action="store_true")
    ap.add_argument("--skip-commons-search", action="store_true")
    ap.add_argument("--slug", action="append", default=[], help="Only these slugs")
    ap.add_argument("--allow-remote", action="store_true",
                    help="If download is rate-limited, store Wikimedia thumb URL in catalog")
    args = ap.parse_args()

    people = json.loads(PEOPLE.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    catalog = load_catalog()
    by_id = {c["id"]: c for c in catalog}
    on_disk = {p.stem for p in OUT_DIR.glob("*")}

    missing = []
    for person in people:
        slug = person.get("slug") or ""
        if slug in SKIP_SLUGS:
            continue
        if args.slug and slug not in args.slug:
            continue
        if person["id"] in by_id and has_usable_portrait(by_id[person["id"]]):
            continue
        if slug in on_disk:
            continue
        missing.append(person)

    if args.limit:
        missing = missing[: args.limit]

    print(f"missing to search: {len(missing)}")
    ok = fail = skip = 0
    remaining = list(missing)

    # Phase 1: batch Wikipedia free pageimages by language
    for lang in ("en", "ru", "de", "fr", "it", "pl", "es", "ja"):
        still = [p for p in remaining if lang in (p.get("wiki_titles") or {})]
        if not still:
            continue
        mapping = {
            urllib.parse.unquote((p["wiki_titles"][lang]).replace("_", " ")): p for p in still
        }
        # also keep underscore form
        mapping.update({p["wiki_titles"][lang]: p for p in still})
        print(f"phase1 pageimages lang={lang} candidates={len(still)}")
        try:
            found = batch_pageimages(lang, mapping)
        except Exception as e:
            print(f"  pageimage batch error: {e}")
            found = {}
        keep = []
        for person in remaining:
            if person["id"] in found:
                file_title, info = found[person["id"]]
                try:
                    item = commit_portrait(
                        person, file_title, info, "wikipedia-pageimage",
                        dry_run=args.dry_run, allow_remote=args.allow_remote,
                    )
                    by_id[item["id"]] = item
                    if not args.dry_run:
                        save_catalog(list(by_id.values()))
                    ok += 1
                    print(f"  OK pageimage {person['slug']} :: {file_title}")
                except Exception as e:
                    fail += 1
                    print(f"  FAIL download {person['slug']}: {e}")
                    keep.append(person)
            else:
                keep.append(person)
        remaining = keep
        time.sleep(0.4)

    # Phase 2: batch Wikidata P18
    print(f"phase2 wikidata P18 remaining={len(remaining)}")
    p18_map = batch_wikidata_p18(remaining) if remaining else {}
    infos = batch_imageinfo(list(p18_map.values())) if p18_map else {}
    keep = []
    for person in remaining:
        file_title = p18_map.get(person["id"])
        if not file_title:
            keep.append(person)
            continue
        try:
            info = infos.get(file_title) or infos.get(file_title.replace("File:", ""))
            if not info or not license_ok(info)[0]:
                keep.append(person)
                continue
            item = commit_portrait(
                person, file_title, info, "wikidata-P18",
                dry_run=args.dry_run, allow_remote=args.allow_remote,
            )
            by_id[item["id"]] = item
            if not args.dry_run:
                save_catalog(list(by_id.values()))
            ok += 1
            print(f"  OK P18 {person['slug']} :: {file_title}")
        except Exception as e:
            fail += 1
            print(f"  FAIL P18 {person['slug']}: {e}")
            keep.append(person)
    remaining = keep

    # Phase 3: careful Commons filename search
    if not args.skip_commons_search:
        print(f"phase3 commons-search remaining={len(remaining)}")
        keep = []
        for i, person in enumerate(remaining, 1):
            names = display_names(person)
            print(f"  [{i}/{len(remaining)}] {person['slug']}")
            try:
                picked = pick_commons_candidate(names)
                if picked:
                    file_title, info = picked
                    item = commit_portrait(
                        person, file_title, info, "commons-search",
                        dry_run=args.dry_run, allow_remote=args.allow_remote,
                    )
                    by_id[item["id"]] = item
                    if not args.dry_run:
                        save_catalog(list(by_id.values()))
                    ok += 1
                    print(f"    OK {file_title} ({item['license']})")
                else:
                    keep.append(person)
                    print("    none")
            except Exception as e:
                fail += 1
                keep.append(person)
                print(f"    FAIL {e}")
            time.sleep(0.3)
        remaining = keep

    # Phase 4: Openverse
    if not args.no_openverse and remaining:
        print(f"phase4 openverse remaining={len(remaining)}")
        keep = []
        for person in remaining:
            names = display_names(person)
            try:
                ov = pick_openverse_candidate(names)
                if ov:
                    item = catalog_item_from_openverse(person, ov)
                    dest = ROOT / "docs" / item["file"]
                    if not args.dry_run:
                        if not dest.exists():
                            download(ov["url"], dest)
                        by_id[item["id"]] = item
                        save_catalog(list(by_id.values()))
                    ok += 1
                    print(f"  OK openverse {person['slug']}")
                else:
                    keep.append(person)
            except Exception as e:
                fail += 1
                keep.append(person)
                print(f"  FAIL openverse {person['slug']}: {e}")
        remaining = keep

    skip = len(remaining)
    if remaining:
        print("still missing:")
        for p in remaining:
            names = display_names(p)
            print(f"  - {p['slug']} | {names[0] if names else '?'}")

    print(f"done: ok={ok} skip={skip} fail={fail} catalog={len(by_id)}")


if __name__ == "__main__":
    main()
