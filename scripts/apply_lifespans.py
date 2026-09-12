#!/usr/bin/env python3
"""Insert/normalize birth–death years next to person wiki links in ru.md / en.md.

Rules:
  - deceased: YYYY–YYYY (en dash)
  - living: RU «р. YYYY», EN «b. YYYY» (no «жив» / «alive» markers)
  - never invent years; only use docs/media/lifespans.json
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
LIFESPANS = ROOT / "docs" / "media" / "lifespans.json"
PEOPLE = ROOT / "docs" / "media" / "people_index.json"

# Link with balanced one-level parens in URL (Andrew_Irvine_(mountaineer))
LINK_RE = re.compile(
    r"\[([^\]]+)\]\((https?://(?:[^()\s]+|\([^()]*\))+)\)"
)

YEAR_RANGE_RE = re.compile(r"\b(1[89]\d{2}|20\d{2})\s*[–—\-]\s*(1[89]\d{2}|20\d{2})\b")
BIRTH_RU_RE = re.compile(r"(?:^|[\s,;])р\.\s*(1[89]\d{2}|20\d{2})\b", re.I)
BIRTH_EN_RE = re.compile(r"(?:^|[\s,;])b\.\s*(1[89]\d{2}|20\d{2})\b", re.I)

NON_PERSON_HINT = re.compile(
    r"(stolb|столб|profile|obituary|comercio|espectador|climb.?za|tnf.?bio|^site$)",
    re.I,
)


def load_url_map() -> dict[str, dict]:
    people = {p["slug"]: p for p in json.load(open(PEOPLE)) if p.get("slug")}
    lives = {r["slug"]: r for r in json.load(open(LIFESPANS))}
    by_url: dict[str, dict] = {}

    def norm(url: str) -> str:
        u = urlparse(url.strip())
        path = unquote(u.path)
        return f"{u.scheme}://{u.netloc}{path}"

    for slug, life in lives.items():
        if not life.get("birth"):
            continue
        p = people.get(slug) or {}
        urls = list(p.get("urls") or [])
        if life.get("wiki"):
            urls.append(life["wiki"])
        for url in urls:
            if "wikipedia.org/wiki/" not in url:
                continue
            by_url[norm(url)] = life
            # also without scheme variants
            by_url[norm(url).replace("https://", "http://")] = life
    return by_url


def year_token(life: dict, lang: str) -> str:
    b, d = life.get("birth"), life.get("death")
    if not b:
        return ""
    if d:
        return f"{b}–{d}"
    return f"р. {b}" if lang == "ru" else f"b. {b}"


def paren_has_years(content: str, lang: str) -> bool:
    if YEAR_RANGE_RE.search(content):
        return True
    if lang == "ru" and BIRTH_RU_RE.search(content):
        return True
    if lang == "en" and BIRTH_EN_RE.search(content):
        return True
    return False


def ensure_years_in_paren(content: str, life: dict, lang: str) -> str:
    """Put lifespan into an existing parenthesis group without duplicating."""
    token = year_token(life, lang)
    if not token:
        return content

    # Already has correct range or birth marker with this year
    if life.get("death"):
        if re.search(rf"\b{life['birth']}\s*[–—\-]\s*{life['death']}\b", content):
            return content
        # Replace wrong/partial range if one exists
        if YEAR_RANGE_RE.search(content):
            return YEAR_RANGE_RE.sub(token, content, count=1)
    else:
        if lang == "ru" and re.search(rf"р\.\s*{life['birth']}\b", content):
            return content
        if lang == "en" and re.search(rf"b\.\s*{life['birth']}\b", content, re.I):
            return content
        content2 = re.sub(r"р\.\s*(1[89]\d{2}|20\d{2})\b", token, content, count=1, flags=re.I)
        if content2 != content:
            return content2
        content2 = re.sub(r"\bb\.\s*(1[89]\d{2}|20\d{2})\b", token, content, count=1, flags=re.I)
        if content2 != content:
            return content2

    if paren_has_years(content, lang):
        return content

    # No years yet: append after first country-like chunk
    content = content.strip()
    if not content:
        return token
    # If starts with country then comma: insert after first clause
    # «СССР» / «USA» / «France/Bolivia, …»
    if "," in content:
        head, tail = content.split(",", 1)
        return f"{head.strip()}, {token},{tail}" if tail.strip() else f"{head.strip()}, {token}"
    # «Австрия» alone or «Austria; *discipline*»
    if ";" in content:
        head, tail = content.split(";", 1)
        return f"{head.strip()}, {token};{tail}"
    return f"{content}, {token}"


def apply_to_text(text: str, lang: str, by_url: dict[str, dict]) -> tuple[str, dict]:
    stats = {"links": 0, "updated": 0, "inserted": 0, "skipped_no_life": 0, "skipped_nonperson": 0}

    def norm(url: str) -> str:
        u = urlparse(url.strip())
        return f"{u.scheme}://{u.netloc}{unquote(u.path)}"

    out = []
    pos = 0
    for m in LINK_RE.finditer(text):
        out.append(text[pos : m.start()])
        name, url = m.group(1), m.group(2)
        full = m.group(0)
        stats["links"] += 1
        life = by_url.get(norm(url))
        if not life or not life.get("birth"):
            if "wikipedia.org/wiki/" in url:
                stats["skipped_no_life"] += 1
            out.append(full)
            pos = m.end()
            continue
        if NON_PERSON_HINT.search(name) or NON_PERSON_HINT.search(url):
            stats["skipped_nonperson"] += 1
            out.append(full)
            pos = m.end()
            continue

        # Inspect suffix after link
        after = text[m.end() :]
        # optional closing bold markers right after link
        bold_suffix = ""
        bm = re.match(r"(\*+)", after)
        # Don't consume ** that close a wrapping bold if years should be inside bold.
        # Common patterns:
        #   **[Name](url)** (years) —
        #   **[Name](url) (years)** —
        # Prefer putting years inside the same visual group when a paren follows soon.

        # Case A: `** (…)` or ` (` immediately after the link
        pm = re.match(r"(\**)(\s*)\(([^)]*)\)", after)
        if pm and len(pm.group(1)) <= 4 and len(pm.group(2)) <= 2 and len(pm.group(3)) <= 180:
            stars, sp, content = pm.group(1), pm.group(2), pm.group(3)
            new_content = ensure_years_in_paren(content, life, lang)
            if new_content != content:
                stats["updated"] += 1
            out.append(full)
            out.append(f"{stars}{sp}({new_content})")
            pos = m.end() + pm.end()
            continue

        # Case B: no suitable paren — insert years after link, before trailing ** if any
        # If after starts with **, keep years before ** when pattern is **[N](u) (y)** 
        # Standard: insert ` (token)` right after URL close.
        token = year_token(life, lang)
        # Avoid double-insert if token already in the next 60 chars
        window = after[:80]
        if token and token in window:
            out.append(full)
            pos = m.end()
            continue
        if token and paren_has_years(window, lang):
            out.append(full)
            pos = m.end()
            continue

        out.append(full + f" ({token})")
        stats["inserted"] += 1
        pos = m.end()

    out.append(text[pos:])
    return "".join(out), stats


def main() -> None:
    by_url = load_url_map()
    print(f"url map size: {len(by_url)}")
    for lang in ("ru", "en"):
        path = ROOT / "docs" / "content" / f"{lang}.md"
        text = path.read_text(encoding="utf-8")
        new, stats = apply_to_text(text, lang, by_url)
        path.write_text(new, encoding="utf-8")
        print(lang, stats)


if __name__ == "__main__":
    main()
