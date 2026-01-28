#!/usr/bin/env python3
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import bibtexparser
from bibtexparser.bparser import BibTexParser
from pylatexenc.latex2text import LatexNodes2Text

_LATEX = LatexNodes2Text()

DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"<>]+", re.I)

def _latex_to_text(s: str | None) -> str:
    """
    Convert common BibTeX/LaTeX markup to readable Unicode text.
    - Decodes accents (No{\"e}l -> Noël)
    - Converts simple math (\beta -> β)
    - Drops formatting commands (\emph{via} -> via)
    """
    s = _clean(s)
    if not s:
        return ""

    # bibtex often wraps bits in { ... } to preserve capitalization
    # pylatexenc handles most, but we also remove stray braces after conversion.
    try:
        txt = _LATEX.latex_to_text(s)
    except Exception:
        txt = s

    # remove lingering braces that sometimes survive
    txt = txt.replace("{", "").replace("}", "")
    # collapse excessive whitespace
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt

def _clean(s: str | None) -> str:
    return (s or "").strip()


def _first_doi(s: str | None) -> str | None:
    s = _clean(s)
    if not s:
        return None
    m = DOI_RE.search(s)
    return m.group(0) if m else None


def _parse_year(s: str | None) -> int:
    s = _clean(s)
    m = re.search(r"\b(19|20)\d{2}\b", s)
    return int(m.group(0)) if m else 0


def _parse_date(entry: dict[str, Any]) -> Optional[date]:
    """
    Try a few BibTeX-ish patterns:
    - date = {2024-06-15}
    - year/month/day fields
    - month as number or name (jan/feb/...)
    """
    d = _clean(entry.get("date"))
    if d:
        # keep only leading YYYY-MM-DD if present
        m = re.match(r"^\s*(\d{4})-(\d{2})-(\d{2})", d)
        if m:
            y, mo, da = map(int, m.groups())
            return date(y, mo, da)
        # sometimes just YYYY-MM
        m = re.match(r"^\s*(\d{4})-(\d{2})", d)
        if m:
            y, mo = map(int, m.groups())
            return date(y, mo, 1)

    y = _parse_year(entry.get("year"))
    if not y:
        return None

    month_raw = _clean(entry.get("month"))
    day_raw = _clean(entry.get("day"))

    month_map = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }

    mo = 1
    if month_raw:
        if month_raw.isdigit():
            mo = max(1, min(12, int(month_raw)))
        else:
            mo = month_map.get(month_raw.lower().strip("."), 1)

    da = 1
    if day_raw and day_raw.isdigit():
        da = max(1, min(31, int(day_raw)))

    return date(y, mo, da)

def _normalize_pages(pages: str) -> str:
    pages = _clean(pages)
    if not pages:
        return ""
    # BibTeX page ranges use double hyphen
    return pages.replace("--", "-")
    # If you prefer en dash: return pages.replace("--", "–")

def _split_authors(author_field: str) -> list[str]:
    return [a.strip().strip(",") for a in author_field.split(" and ") if a.strip()]


def _format_one_author(name: str) -> str:
    """
    Convert "Last, First Middle" or "First Middle Last" -> "Last, F. M."
    """
    name = _latex_to_text(name).strip().strip(",")
    if not name:
        return ""

    if "," in name:
        last, given = [p.strip() for p in name.split(",", 1)]
    else:
        bits = name.split()
        if len(bits) == 1:
            return bits[0]
        last = bits[-1]
        given = " ".join(bits[:-1])

    initials: list[str] = []
    for tok in re.split(r"[\s\-]+", given):
        tok = tok.strip().strip(".").strip(",")
        if not tok:
            continue
        initials.append(tok[0].upper() + ".")

    if initials:
        return f"{last}, {' '.join(initials)}"
    return last


def _format_author_list(author_field: str) -> str:
    authors = [_format_one_author(a) for a in _split_authors(author_field)]
    authors = [a for a in authors if a]
    if not authors:
        return ""

    if len(authors) == 1:
        return authors[0]

    if len(authors) == 2:
        # matches house style: "A and B"
        return f"{authors[0]} and {authors[1]}"

    # matches examples: semicolons, and “; and” before last
    return "; ".join(authors[:-1]) + " and " + authors[-1]


def _doi_href(doi: str, url: str | None) -> str:
    """
    If url looks like a DOI landing page and contains the DOI, prefer it (e.g., Science).
    Else default to https://doi.org/<doi>.
    """
    url = _clean(url)
    if url and doi.lower() in url.lower() and ("doi" in url.lower() or "10." in url):
        return url
    return f"https://doi.org/{doi}"


def _doi_anchor(doi: str, href: str) -> str:
    doi = html.escape(doi)
    href = html.escape(href, quote=True)
    return f'<a href="{href}">{doi}</a>'

def _extract_preprint_doi(entry: dict[str, Any]) -> str | None:
    """
    Extract preprint_doi from either:
      - a dedicated field (if present)
      - or from annotation like: 'preprint_doi:10.26434/...'
    """
    # Preferred: explicit field
    direct = entry.get("preprint_doi")
    if direct:
        return _first_doi(direct)

    annotation = _clean(entry.get("annotation"))
    if not annotation:
        return None

    # Look for preprint_doi:10....
    m = re.search(r"preprintdoi\s*:\s*(10\.\d{4,9}/[^\s,;]+)", annotation, re.I)
    if m:
        return m.group(1)

    return None

def _infer_journal(entry: dict[str, Any], doi: str | None) -> str:
    """
    Infer journal/container when missing.
    Currently handles ChemRxiv preprints.
    """
    journal = _clean(
        entry.get("journal")
        or entry.get("booktitle")
        or entry.get("howpublished")
    )

    if journal:
        return journal

    if doi and doi.lower().startswith("10.26434/chemrxiv"):
        return "ChemRxiv"

    return ""

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
    doi_url: str | None
    preprint_doi: str | None
    published_date: Optional[date]

    @staticmethod
    def from_bib(e: dict[str, Any]) -> "Entry":
        year = _parse_year(e.get("year"))
        doi = _first_doi(e.get("doi"))
        preprint_doi = _extract_preprint_doi(e)
        published_date = _parse_date(e)

        return Entry(
            key=_clean(e.get("ID")),
            entrytype=_clean(e.get("ENTRYTYPE")),
            title=_clean(e.get("title")),
            author=_clean(e.get("author")),
            journal=_infer_journal(e, doi),
            year=year,
            volume=_clean(e.get("volume")),
            pages=_clean(e.get("pages")),
            doi=doi,
            doi_url=_clean(e.get("url")) or None,
            preprint_doi=preprint_doi,
            published_date=published_date,
        )

    def sort_key(self):
        # newest first: use full date if available; else Jan 1 of year; else very old
        d = self.published_date or (date(self.year, 1, 1) if self.year else date(1900, 1, 1))
        return (d, self.title.lower())

    def render_html_entry(self) -> str:
        """
        Match your target house HTML as close as possible.

        Pattern:
        Authors. Title <em> Journal</em>, <strong>YEAR</strong>, <em>VOLUME,</em> PAGES, DOI: <a href="...">DOI</a> (For the preprint version, see <a ...>DOI</a>)
        """
        authors = _latex_to_text(_format_author_list(self.author))
        title = html.escape(_latex_to_text(self.title))
        journal = html.escape(_latex_to_text(self.journal))

        year = str(self.year) if self.year else ""
        volume = html.escape(self.volume)
        pages = html.escape(_normalize_pages(self.pages))

        parts: list[str] = []
        if authors:
            parts.append(f"{html.escape(authors)}")
        if title:
            parts.append(title)

        # Journal is italic, with a leading space INSIDE <em> to match examples: <em> Matter</em>
        if journal:
            parts.append(f"<em> {journal}</em>,")
        if year:
            parts.append(f"<strong>{html.escape(year)}</strong>, ")

        # volume in italics with trailing comma inside the <em> tag: <em>7,</em>
        if volume:
            parts.append(f"<em>{volume}, </em>")

        # pages are plain, followed by comma
        if pages:
            parts.append(f"{pages}, ")

        # DOI block
        if self.doi:
            href = _doi_href(self.doi, self.doi_url)
            parts.append(f"DOI: {_doi_anchor(self.doi, href)}")

        # Join with spaces, then clean comma spacing a bit
        txt = " ".join([p for p in parts if p]).strip()
        txt = re.sub(r"\s+,", ",", txt)  # avoid " ,"
        txt = re.sub(r",\s*,", ",", txt)

        # Preprint note, exactly as your example
        if self.preprint_doi:
            pre_href = f"https://doi.org/{self.preprint_doi}"
            txt += f' (For the preprint version, see {_doi_anchor(self.preprint_doi, pre_href)})'

        return f'<div class="csl-entry">{txt}</div>'


def load_entries(bib_path: Path) -> list[Entry]:
    parser = BibTexParser(common_strings=True)
    with bib_path.open("r", encoding="utf-8") as f:
        db = bibtexparser.load(f, parser=parser)
    return [Entry.from_bib(e) for e in db.entries]


def build_html(entries: list[Entry]) -> str:
    # sort by date (newest first)
    entries = sorted(entries, key=lambda e: e.sort_key(), reverse=True)

    # group by year (descending)
    by_year: dict[int, list[Entry]] = {}
    for e in entries:
        if e.year:
            by_year.setdefault(e.year, []).append(e)

    years = sorted(by_year.keys(), reverse=True)

    blocks: list[str] = []
    blocks.append('<div class="csl-bib-body">')

    for y in years:
        blocks.append(f'<h2 class="wpmgrouptitle">{y}</h2>')
        for e in by_year[y]:
            blocks.append(e.render_html_entry())

    blocks.append("</div>")
    return "\n".join(blocks)


def main() -> None:
    root = Path(__file__).resolve().parent
    bib = root / "publications.bib"
    out = root / "publications.html"

    entries = load_entries(bib)
    html_out = build_html(entries)

    out.write_text(html_out + "\n", encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()