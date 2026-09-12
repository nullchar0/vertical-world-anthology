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
link_re = re.compile(r"\*\*\[([^\]]+)\]\((https?://[^)]+)\)")


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
            if lang not in rec["names"] or len(name) > len(rec["names"][lang]):
                rec["names"][lang] = name
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
        if "slug" not in p:
            n = p["names"].get("en") or p["names"].get("ru") or "person"
            p["slug"] = slugify(n)
    OUT.write_text(json.dumps(list(people.values()), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(people)} people -> {OUT}")


if __name__ == "__main__":
    main()
