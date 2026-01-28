#!/usr/bin/env python3
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import bibtexparser
import requests

DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"<>]+", re.I)


def _clean(s: str | None) -> str:
    return (s or "").strip()


def _first_doi(s: str | None) -> str | None:
    s = _clean(s)
    if not s:
        return None
    m = DOI_RE.search(s)
    return m.group(0) if m else None


def _parse_year(s: str | None) -> str:
    s = _clean(s)
    m = re.search(r"\b(19|20)\d{2}\b", s)
    return m.group(0) if m else ""


def _normalize_pages(p: str) -> str:
    p = _clean(p)
    return p.replace("--", "-") if p else ""


@dataclass
class BibItem:
    key: str
    doi: str
    title: str
    journal: str
    year: str
    volume: str
    issue: str
    pages: str
    url: str


def load_bib(path: Path) -> list[BibItem]:
    parser = bibtexparser.bparser.BibTexParser(common_strings=True)
    with path.open("r", encoding="utf-8") as f:
        db = bibtexparser.load(f, parser=parser)

    items: list[BibItem] = []
    for e in db.entries:
        doi = _first_doi(e.get("doi"))
        if not doi:
            continue

        items.append(
            BibItem(
                key=_clean(e.get("ID")),
                doi=doi,
                title=_clean(e.get("title")),
                journal=_clean(e.get("journal") or e.get("booktitle") or e.get("howpublished")),
                year=_parse_year(e.get("year")),
                volume=_clean(e.get("volume")),
                issue=_clean(e.get("number") or e.get("issue")),
                pages=_normalize_pages(e.get("pages")),
                url=_clean(e.get("url")),
            )
        )
    return items


def crossref_lookup(doi: str) -> dict[str, Any] | None:
    url = f"https://api.crossref.org/works/{doi}"
    r = requests.get(
        url,
        timeout=25,
        headers={
            # Crossref asks for a UA that identifies you; replace email if you want
            "User-Agent": "NRG-publications-metadata-watch/1.0 (mailto:your-email@example.com)"
        },
    )
    if r.status_code != 200:
        return None
    data = r.json()
    return data.get("message") or None


def cr_get_first(msg: dict[str, Any], field: str) -> str:
    v = msg.get(field)
    if isinstance(v, list):
        return _clean(v[0]) if v else ""
    return _clean(str(v)) if v is not None else ""


def cr_year(msg: dict[str, Any]) -> str:
    dp = (msg.get("issued") or {}).get("date-parts") or []
    if dp and dp[0] and isinstance(dp[0][0], int):
        return str(dp[0][0])
    return ""


def compare(item: BibItem, msg: dict[str, Any]) -> dict[str, tuple[str, str]]:
    diffs: dict[str, tuple[str, str]] = {}

    cr_title = cr_get_first(msg, "title")
    cr_journal = cr_get_first(msg, "container-title")
    cr_vol = _clean(msg.get("volume"))
    cr_issue = _clean(msg.get("issue"))
    cr_pages = _normalize_pages(_clean(msg.get("page")))
    cr_url = _clean(msg.get("URL"))
    cr_y = cr_year(msg)

    def chk(field: str, bib_val: str, cr_val: str) -> None:
        if _clean(cr_val) and _clean(bib_val) != _clean(cr_val):
            diffs[field] = (bib_val, cr_val)

    # Only flag fields if Crossref actually has a value for them
    chk("year", item.year, cr_y)
    chk("volume", item.volume, cr_vol)
    chk("issue", item.issue, cr_issue)
    chk("pages", item.pages, cr_pages)

    # URL is optional; only compare if you have set one in BibTeX
    if item.url:
        chk("url", item.url, cr_url)

    return diffs


def build_report(diffs_by_key: dict[str, dict[str, tuple[str, str]]]) -> str:
    lines: list[str] = []
    lines.append("# Metadata watch report\n")
    lines.append(f"Generated: **{date.today().isoformat()}**\n")

    if not diffs_by_key:
        lines.append("No differences detected vs Crossref.\n")
        return "\n".join(lines)

    lines.append(f"Found differences for **{len(diffs_by_key)}** item(s).\n")

    for key, diffs in diffs_by_key.items():
        lines.append(f"## `{key}`\n")
        for field, (bib_v, cr_v) in diffs.items():
            lines.append(f"- **{field}**")
            lines.append(f"  - bib: `{bib_v}`")
            lines.append(f"  - cr:  `{cr_v}`\n")

    return "\n".join(lines)


def main() -> int:
    bib_path = Path("publications.bib")
    out_path = Path("metadata_report.md")

    items = load_bib(bib_path)
    diffs_by_key: dict[str, dict[str, tuple[str, str]]] = {}

    for it in items:
        msg = crossref_lookup(it.doi)
        if not msg:
            continue
        diffs = compare(it, msg)
        if diffs:
            diffs_by_key[it.key] = diffs

    report = build_report(diffs_by_key)
    out_path.write_text(report + "\n", encoding="utf-8")

    # Exit code 1 means "diffs found"
    return 1 if diffs_by_key else 0


if __name__ == "__main__":
    raise SystemExit(main())