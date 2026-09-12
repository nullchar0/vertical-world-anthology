#!/usr/bin/env python3
"""Build docs/media/people_index.json from public RU/EN markdown."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "media" / "people_index.json"
link_re = re.compile(
    r"(?:\*\*)?\[([^\]]+)\]\((https?://(?:[^()\s]+|\([^()]*\))+)\)"
)

# Russian declined forms often sneak in from mid-sentence links («с Алексом Хоннольдом»)
DECLINED_RE = re.compile(
    r"(?:ом|ым|ой|ей|ею|ую|ого|ему|ими|ами|ах|ях)$",
    re.I,
)


def slugify(s: str) -> str:
    s = unquote(s)
    s = unicodedata.normalize("NFKC", s).strip().lower().replace("ё", "е")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    table = str.maketrans({
        "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ж":"zh","з":"z","и":"i","й":"y",
        "к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u",
        "ф":"f","х":"h","ц":"ts","ч":"ch","ш":"sh","щ":"sch","ъ":"","ы":"y","ь":"","э":"e",
        "ю":"yu","я":"ya",
    })
    s = s.translate(table)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:80] or hashlib.md5(s.encode()).hexdigest()[:12]


def name_from_wiki_title(title: str) -> str:
    t = unquote(title).replace("_", " ").strip()
    t = re.sub(r"\s*\(.*?\)\s*", " ", t).strip()
    if "," in t:
        last, first = [x.strip() for x in t.split(",", 1)]
        if first and last:
            return f"{first} {last}".strip()
    return t


def looks_declined(name: str) -> bool:
    parts = name.strip().split()
    if len(parts) < 2:
        return False
    # «Алексом Хоннольдом», «с Макарти-Снейпом» style
    return all(DECLINED_RE.search(p.replace("-", "")) for p in parts[-2:])


def prefer_name(old: str | None, new: str) -> str:
    if not old:
        return new
    if looks_declined(old) and not looks_declined(new):
        return new
    if looks_declined(new) and not looks_declined(old):
        return old
    # Prefer wiki-ish shorter nominative over long declined phrases
    if looks_declined(new):
        return old
    if len(new) > len(old) and not looks_declined(new):
        return new
    return old


def main() -> None:
    people: dict[str, dict] = {}
    for lang in ("ru", "en"):
        text = (ROOT / "docs" / "content" / f"{lang}.md").read_text(encoding="utf-8")
        for m in link_re.finditer(text):
            name, url = m.group(1).strip(), m.group(2).strip()
            if "wikipedia.org/wiki/" in url:
                title = url.split("/wiki/")[-1].split("#")[0]
                key = "wiki:" + title
            else:
                key = "ext:" + hashlib.md5(url.encode()).hexdigest()[:12]
            rec = people.setdefault(key, {"id": key, "names": {}, "urls": [], "wiki_titles": {}})
            rec["names"][lang] = prefer_name(rec["names"].get(lang), name)
            if url not in rec["urls"]:
                rec["urls"].append(url)
            if "wikipedia.org/wiki/" in url:
                host = url.split("//")[1].split("/")[0]
                langcode = host.split(".")[0]
                if langcode in ("www",):
                    langcode = "en"
                title = unquote(url.split("/wiki/")[-1].split("#")[0])
                rec["wiki_titles"][langcode] = title
                if "slug" not in rec:
                    rec["slug"] = slugify(unquote(title.replace("_", " ")))

    for p in people.values():
        # Prefer nominative forms derived from Wikipedia titles
        wt = p.get("wiki_titles") or {}
        if "en" in wt:
            en = name_from_wiki_title(wt["en"])
            if en and (looks_declined(p["names"].get("en", "")) or not p["names"].get("en")):
                p["names"]["en"] = en
            elif en and not p["names"].get("en"):
                p["names"]["en"] = en
            if en and "en" in p["names"]:
                p["names"]["en"] = prefer_name(p["names"]["en"], en)
        if "ru" in wt:
            ru = name_from_wiki_title(wt["ru"])
            if ru:
                p["names"]["ru"] = prefer_name(p["names"].get("ru"), ru)
        # If RU name still looks declined but EN exists, transliteration fallback is hard —
        # at least drop obvious instrumental duplicates by preferring EN-shaped wiki ru title
        if looks_declined(p["names"].get("ru", "")) and "en" in wt:
            # Keep EN; for RU try reversing "Honnold, Alex" style from en title into a clean form
            # if ru wiki missing: use EN nominative as temporary display for RU too is wrong.
            pass
        if "slug" not in p:
            n = p["names"].get("en") or p["names"].get("ru") or "person"
            p["slug"] = slugify(n)

    # Hard overrides for known bad declines when wiki title is awkward
    overrides = {
        "honnold-aleks": {"ru": "Алекс Хоннольд", "en": "Alex Honnold"},
        "hansjorg-auer": {"ru": "Хансйорг Ауэр", "en": "Hansjörg Auer"},
    }
    for p in people.values():
        o = overrides.get(p.get("slug") or "")
        if o:
            p["names"].update(o)

    OUT.write_text(json.dumps(list(people.values()), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(people)} people -> {OUT}")


if __name__ == "__main__":
    main()
