# NRG_BIB

> ***"You keep using that word. I do not think it means what you think it means."***  
> — *Inigo Montoya (The Princess Bride)*

---

## Overview

### What it is:
**NRG_BIB** is the canonical bibliography repository for the Noël Research Group. It maintains the master BibTeX database (`publications.bib`) and a set of Python tools that automatically render it into a publication list (`publications.html`) ready to embed on the group website.

The repository does two things:
- **Build**: `build_publications.py` parses the `.bib` file, formats author lists, resolves LaTeX/Unicode, sorts by date, and writes a structured HTML snippet grouped by year.
- **Check**: `check_metadata.py` cross-references every DOI against the Crossref API and reports any discrepancies in volume, issue, pages, or year.

---

## Table of Contents

- [Why a shared bib?](#why-a-shared-bib)
- [Repository Structure](#repository-structure)
- [Installation and Setup](#installation-and-setup)
- [Usage](#usage)
  - [Building the HTML](#building-the-html)
  - [Checking Metadata](#checking-metadata)
- [Adding a Publication](#adding-a-publication)
- [BibTeX Conventions](#bibtex-conventions)
- [Contributing](#contributing)
- [License](#license)
- [Author](#author)

---

## Why a shared bib?

Scattered, per-project `.bib` files diverge quickly — wrong page numbers, inconsistent author formatting, missing DOIs. A single source of truth means the group website, papers, and CVs all draw from the same validated database.

---

## Repository Structure

```plaintext
NRG_BIB
├── publications.bib        # Master BibTeX database
├── publications.html       # Auto-generated HTML output (do not edit by hand)
├── build_publications.py   # Bib → HTML renderer
├── check_metadata.py       # Crossref metadata validator
└── LICENSE
```

---

## Installation and Setup

### Requirements

- **Python 3.12+**
- **pip** packages:

```bash
pip install bibtexparser pylatexenc requests
```

No conda environment is required — a lightweight virtual environment is sufficient.

---

## Usage

### Building the HTML

```bash
python build_publications.py
```

This reads `publications.bib` and writes `publications.html`. The output is a self-contained `<div class="csl-bib-body">` block, grouped by year (newest first), ready to paste into the group website.

### Checking Metadata

```bash
python check_metadata.py
```

Queries Crossref for every entry that has a DOI and compares `year`, `volume`, `issue`, and `pages` against what is recorded in the `.bib` file. A report is written to `metadata_report.md`. Exit code `1` means differences were found; `0` means everything matches.

---

## Adding a Publication

1. Add the entry to `publications.bib` following the conventions below.
2. Run `python check_metadata.py` to verify metadata is correct.
3. Run `python build_publications.py` to regenerate `publications.html`.
4. Commit both `publications.bib` and `publications.html`.

---

## BibTeX Conventions

- **Key format**: `firstauthorTitleKeyword{YEAR}` (Zotero default is fine).
- **Required fields**: `author`, `title`, `journal` (or `booktitle`), `year`, `doi`.
- **Month**: use the three-letter abbreviation (`jan`, `feb`, …) or a number.
- **Preprint DOI**: add a `preprint_doi` field (e.g. `preprint_doi = {10.26434/chemrxiv-...}`) to have the renderer append a preprint link automatically.
- **Pages**: use double-hyphen for ranges (`4978--4985`); the renderer normalises to a single hyphen.
- **LaTeX accents**: keep them in the `.bib` file (`No{\"e}l`); the renderer converts them to Unicode on output.

---

## Contributing

1. Fork this repository.
2. Add or correct entries in `publications.bib`.
3. Run the build and check scripts to validate.
4. Open a pull request against `main`.

Do **not** edit `publications.html` by hand — it is always regenerated from the `.bib` file.

---

## License

This project is licensed under the Apache License 2.0. See the LICENSE file for details.

---

## Author

**Elia Savino** — e.savino@uva.nl (2025)  
Noël Research Group, University of Amsterdam
