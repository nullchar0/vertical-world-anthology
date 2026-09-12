#!/usr/bin/env python3
"""Build public markdown for the GitHub Pages site (strip editorial meta)."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

def clean_ru(t: str) -> str:
    t = re.sub(
        r"(# [^\n]+\n\n)>.*?(?=\n## )",
        r"\1> Антология людей вертикального мира (1900–2026): кто задал планку, стиль, технику, этику или публичный образ.\n\n",
        t, count=1, flags=re.S,
    )
    t = re.sub(r"\n## Заметки к редакции\n.*\Z", "\n", t, flags=re.S)
    t = re.sub(r"`?climbing_stars_report_claude\.ORIGINAL\.md`?", "", t)
    t = re.sub(r"Архивная копия ранней версии[^\n]*\n?", "", t)
    t = re.sub(r"Живой документ:[^\n]*\n?", "", t)
    return t.strip() + "\n"

def clean_en(t: str) -> str:
    t = re.sub(
        r"(# [^\n]+\n\n)>.*?(?=\n## )",
        r"\1> An anthology of people in the vertical world (1900–2026): those who set the bar for style, technique, ethics, or public image.\n\n",
        t, count=1, flags=re.S,
    )
    if "## Editorial notes" in t:
        t = t[: t.find("## Editorial notes")].rstrip() + "\n"
    t = re.sub(r"`?climbing_stars_report_claude\.ORIGINAL\.md`?", "", t)
    t = re.sub(r"`?climbing_stars_anthology\.md`?", "", t)
    t = re.sub(r"Archival copy of an earlier version:[^\n]*\n?", "", t)
    t = re.sub(r"A living document:[^\n]*\n?", "", t)
    t = re.sub(r"English translation of the Russian anthology[^\n]*\n?", "", t)
    return t.strip() + "\n"

def main():
    out = ROOT / "docs" / "content"
    out.mkdir(parents=True, exist_ok=True)
    (out / "ru.md").write_text(clean_ru((ROOT / "climbing_stars_anthology.md").read_text(encoding="utf-8")), encoding="utf-8")
    (out / "en.md").write_text(clean_en((ROOT / "climbing_stars_anthology_en.md").read_text(encoding="utf-8")), encoding="utf-8")
    print("wrote", out / "ru.md", out / "en.md")

if __name__ == "__main__":
    main()
