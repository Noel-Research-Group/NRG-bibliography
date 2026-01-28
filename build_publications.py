#!/usr/bin/env python3
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import bibtexparser
from bibtexparser.bparser import BibTexParser

DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"<>]+", re.I)


def _clean(s: str | None) -> str:
    return (s or "").strip()


def _first_doi(s: str) -> str | None:
    s = _clean(s)
    if not s:
        return None
    m = DOI_RE.search(s)
    return m.group(0) if m else None


def _doi_link(doi: str) -> str:
    doi = doi.strip()
    url = f"https://doi.org/{doi}"
    # clickable but displays "DOI: 10...."
    return f'<a href="{url}" target="_blank" rel="noopener">DOI: {doi}</a>'


def _split_authors(author_field: str) -> list[str]:
    # BibTeX "and" separator
    parts = [a.strip() for a in author_field.split(" and ") if a.strip()]
    return parts


def _format_one_author(name: str) -> str:
    """
    Convert "Last, First Middle" or "First Middle Last" to "Last, F. M."
    """
    name = name.strip()
    if "," in name:
        last, first = [p.strip() for p in name.split(",", 1)]
        given = first
    else:
        bits = name.split()
        if len(bits) == 1:
            return bits[0]
        last = bits[-1]
        given = " ".join(bits[:-1])

    initials = []
    for token in re.split(r"[\s\-]+", given):
        token = token.strip().strip(".")
        if not token:
            continue
        initials.append(token[0].upper() + ".")
    if initials:
        return f"{last}, {' '.join(initials)}"
    return last


def _format_author_list(author_field: str) -> str:
    authors = [_format_one_author(a) for a in _split_authors(author_field)]
    if not authors:
        return ""
    if len(authors) == 1:
        return authors[0]
    # semicolons + "and" before last
    return "; ".join(authors[:-1]) + " and " + authors[-1]


@dataclass
class Entry:
    key: str
    entrytype: str
    title: str
    author: str
    journal: str
    year: int
    volume: str
    pages: str
    doi: str | None
    preprint_doi: str | None

    @staticmethod
    def from_bib(e: dict[str, Any]) -> "Entry":
        year_raw = _clean(e.get("year"))
        try:
            year = int(re.findall(r"\d{4}", year_raw)[0])
        except Exception:
            year = 0

        doi = _first_doi(_clean(e.get("doi")))
        preprint_doi = _first_doi(_clean(e.get("preprint_doi")))

        return Entry(
            key=_clean(e.get("ID")),
            entrytype=_clean(e.get("ENTRYTYPE")),
            title=_clean(e.get("title")),
            author=_clean(e.get("author")),
            journal=_clean(e.get("journal") or e.get("booktitle") or e.get("howpublished") or ""),
            year=year,
            volume=_clean(e.get("volume")),
            pages=_clean(e.get("pages")),
            doi=doi,
            preprint_doi=preprint_doi,
        )

    def render_line(self) -> str:
        authors = _format_author_list(self.author)
        parts: list[str] = []
        if authors:
            parts.append(f"{authors}.")
        if self.title:
            parts.append(self.title)
        if self.journal:
            parts.append(self.journal + ",")
        if self.year:
            parts.append(str(self.year) + ",")
        if self.volume:
            parts.append(self.volume + ",")
        if self.pages:
            parts.append(self.pages + ",")
        if self.doi:
            parts.append(_doi_link(self.doi))
        # join with spaces; commas already included above
        txt = " ".join([p for p in parts if p]).strip()
        # clean up any ", ," accidents
        txt = re.sub(r",\s*,", ",", txt)
        txt = txt.replace(" ,", ",")
        return txt

    def render_html(self) -> str:
        main = self.render_line()
        extra = ""
        if self.preprint_doi:
            extra = (
                f' <span class="nrg-note">(Preprint: {_doi_link(self.preprint_doi)})</span>'
            )
        return f'<div class="nrg-pub">{main}{extra}</div>'


def load_entries(bib_path: Path) -> list[Entry]:
    parser = BibTexParser(common_strings=True)
    with bib_path.open("r", encoding="utf-8") as f:
        db = bibtexparser.load(f, parser=parser)
    entries = [Entry.from_bib(e) for e in db.entries]
    return entries


def build_html(entries: list[Entry], title: str = "Publications") -> str:
    # sort: year desc, then title
    entries = sorted(entries, key=lambda e: (-e.year, e.title.lower()))

    # group by year
    years: dict[int, list[Entry]] = {}
    for e in entries:
        years.setdefault(e.year, []).append(e)

    year_keys = sorted([y for y in years.keys() if y], reverse=True)

    blocks: list[str] = []
    blocks.append('<div class="nrg-publications">')
    blocks.append(f"<h1>{title}</h1>")

    for y in year_keys:
        blocks.append(f'<h2 class="wpmgrouptitle">{y}</h2>')
        for e in years[y]:
            blocks.append(e.render_html())

    blocks.append("</div>")
    return "\n".join(blocks)


def main() -> None:
    root = Path(__file__).resolve().parent
    bib = root / "publications.bib"
    out = root / "publications.html"

    entries = load_entries(bib)
    html = build_html(entries, title="Publications")

    out.write_text(html + "\n", encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()