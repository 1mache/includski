#!/usr/bin/env python3
"""Generate `res/mappings.json` from cppreference C++ header pages.

Crawls https://en.cppreference.com/cpp/header for the list of standard
library headers, then visits each header page and pulls the "primary"
symbols (classes, types, macros, constants, enums, objects, concepts) out of
its section tables. Functions, includes, and synopsis rows are skipped, per
the includski product spec (see CLAUDE.md, "Generator" section).

Output files (default: `res/`):
- `mappings.json`: `{"symbol": "<header>", ...}`, written even if some pages
  failed to fetch.
- `scrape-collisions.json`: `{"symbol": {"winner": "<header>", "losers": [...]}}`
  for symbols seen on more than one header page (first index-order header
  wins the map; `winner` duplicates the value already in `mappings.json`, so
  this file is self-contained for reviewing collisions and writing overrides).
- `scrape-errors.json`: `[{"url": ..., "reason": ...}]` for pages that could
  not be fetched after retries.

Exits non-zero if any page failed. Never writes an error string into the
symbol map.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Set as FrozenStrSet
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

BASE_URL: Final = "https://en.cppreference.com"
INDEX_URL: Final = f"{BASE_URL}/cpp/header"
USER_AGENT: Final = "includski-mapping-generator/0.1 (personal VS Code extension)"
REQUEST_TIMEOUT_SECONDS: Final = 30
MAX_ATTEMPTS: Final = 3
DEFAULT_WORKERS: Final = 4

# Only these cppreference section ids hold "primary" entities per CLAUDE.md.
# Functions / Includes / Synopsis / Customization_point_objects / Helpers /
# Defect_reports are deliberately excluded.
KEPT_SECTION_IDS: Final = frozenset(
    {
        "Classes",
        "Types",
        "Type_aliases",
        "Macros",
        "Constants",
        "Enumerations",
        "Objects",
        "Concepts",
    }
)

def _css_classes(tag: Tag) -> list[str]:
    """Normalize a tag's `class` attribute to a list (bs4 types it as str | list[str] | None)."""
    value: str | list[str] = tag.get("class") or []
    return [value] if isinstance(value, str) else value


HEADER_LINK_RE: Final = re.compile(r"^/cpp/header/([^/#?]+)$")
IDENTIFIER_RE: Final = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# The index page's own section id for the "C compatibility headers" group,
# per CLAUDE.md ("C-compat wrapper detection"). Derived from the page's own
# structure at run time (see `wrapper_stems`), not a hand-typed stem list.
WRAPPER_HEADERS_SECTION_ID: Final = "C_compatibility_headers"

RES_DIR: Final = Path(__file__).resolve().parents[1] / "res"
DEFAULT_MAPPINGS_PATH: Final = RES_DIR / "mappings.json"
DEFAULT_GLOBALS_PATH: Final = RES_DIR / "globals.json"
DEFAULT_COLLISIONS_PATH: Final = RES_DIR / "scrape-collisions.json"
DEFAULT_ERRORS_PATH: Final = RES_DIR / "scrape-errors.json"


@dataclass(frozen=True)
class FetchError:
    """A page that could not be fetched after retries."""

    url: str
    reason: str


@dataclass(frozen=True)
class HeaderPage:
    """One cppreference header page: its `<header>` name and stem."""

    stem: str
    header: str  # angle-bracket form, e.g. "<vector>"
    url: str


@dataclass
class ScrapeResult:
    """Accumulated output of a full or partial crawl."""

    mappings: dict[str, str] = field(default_factory=dict)
    collisions: dict[str, list[str]] = field(default_factory=dict)
    errors: list[FetchError] = field(default_factory=list)
    globals_: set[str] = field(default_factory=set)

    def add_symbol(self, symbol: str, header: str) -> None:
        """Record `symbol` as belonging to `header`, first header wins.

        A symbol can repeat many times on one losing header (e.g. every
        `std::hash<std::chrono::X>` specialization collapses to the bare
        symbol `hash`), so losers are deduplicated per symbol.
        """
        existing = self.mappings.get(symbol)
        if existing is None:
            self.mappings[symbol] = header
        elif existing != header and header not in self.collisions.get(symbol, []):
            self.collisions.setdefault(symbol, []).append(header)


def fetch(session: requests.Session, url: str) -> str:
    """GET `url` and return its decoded body, retrying on failure.

    Raises the last `requests` exception if all attempts fail.
    """
    last_error: Exception | None = None
    for _attempt in range(MAX_ATTEMPTS):
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response.text
        except requests.RequestException as error:
            last_error = error
    assert last_error is not None
    raise last_error


def parse_index(html: str) -> list[HeaderPage]:
    """Extract standard-library header pages from the index page HTML.

    Header stems ending in `.h` are C-compat pages and are skipped, per
    CLAUDE.md ("Skip *.h C-compat pages as scrape targets").
    """
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("#mw-content-text") or soup

    pages: list[HeaderPage] = []
    seen_stems: set[str] = set()
    for anchor in content.find_all("a", href=True):
        match = HEADER_LINK_RE.match(str(anchor["href"]))
        if match is None:
            continue
        stem = match.group(1)
        if stem in seen_stems or stem.endswith(".h"):
            continue
        seen_stems.add(stem)
        pages.append(HeaderPage(stem=stem, header=f"<{stem}>", url=f"{BASE_URL}/cpp/header/{stem}"))
    return pages


def _section_id(heading: Tag) -> str | None:
    """Return the `id` of a heading's `span.mw-headline`, if present."""
    headline = heading.find("span", class_="mw-headline")
    if headline is None:
        return None
    section_id = headline.get("id")
    return section_id if isinstance(section_id, str) else None


def wrapper_stems(html: str) -> set[str]:
    """Return header stems listed under the index page's C-compat section.

    Tracks the current section heading while walking the index page, the
    same way `extract_symbols` tracks sections on header pages, and collects
    every linked stem while inside `WRAPPER_HEADERS_SECTION_ID`. Self-sourced
    from the page's own structure, not a hand-typed stem list.
    """
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("#mw-content-text") or soup

    stems: set[str] = set()
    current_section: str | None = None
    for element in content.find_all(["h2", "h3", "a"]):
        if element.name in ("h2", "h3"):
            current_section = _section_id(element)
            continue
        if current_section != WRAPPER_HEADERS_SECTION_ID:
            continue
        href = element.get("href")
        if not isinstance(href, str):
            continue
        match = HEADER_LINK_RE.match(href)
        if match is not None and not match.group(1).endswith(".h"):
            stems.add(match.group(1))
    return stems


def _normalize_symbol(raw_text: str) -> str | None:
    """Turn one `<span>`'s text into a bare identifier, or None to reject it.

    Rejects text containing `<` (template specializations like
    `vector<bool>` or `std::hash<std::vector<bool>>`), collapses `A :: B` to
    `A::B`, keeps only the last `::`-separated component, and requires the
    result to be a plain identifier (drops `operator+`, prose fragments).
    """
    text = " ".join(raw_text.split()).replace(" :: ", "::")
    if "<" in text:
        return None
    last_component = text.split("::")[-1]
    return last_component if IDENTIFIER_RE.fullmatch(last_component) else None


def _row_symbols(row: Tag) -> list[str]:
    """Collect normalized symbol names from one `tr.t-dsc` description row.

    cppreference renders a row's name cell in two shapes:
    - Multiple synonyms sharing one description (`int8_t`/`int16_t`/...,
      `vector`/its hash specialization): a `span.t-lines` group with one
      `<span>` per name.
    - A single name (`std::chrono::milliseconds`, `true_type`), rendered as
      a plain `<a>`, `<code>`, or `span.t-lc` with no `t-lines` wrapper.
    """
    first_cell = row.find("td")
    if not isinstance(first_cell, Tag):
        return []

    name_groups = first_cell.select("span.t-lines")
    if name_groups:
        names: list[str] = []
        for name_group in name_groups:
            for span in name_group.find_all("span", recursive=False):
                if any(cls.startswith("t-mark") for cls in _css_classes(span)):
                    continue
                for version_mark in span.select("span.t-dsc-small"):
                    version_mark.decompose()
                symbol = _normalize_symbol(span.get_text(" ", strip=True))
                if symbol is not None:
                    names.append(symbol)
        return names

    for annotation in first_cell.find_all(True):
        classes = _css_classes(annotation)
        if "editsection" in classes or any(cls.startswith("t-mark") for cls in classes):
            annotation.decompose()
    symbol = _normalize_symbol(first_cell.get_text(" ", strip=True))
    return [symbol] if symbol is not None else []


def extract_symbols(html: str) -> list[str]:
    """Collect primary symbol names from a header page's kept sections.

    Walks the content area in document order, tracking the current `h3`
    section id, and gathers symbols from `tr.t-dsc` rows while that section
    is one of `KEPT_SECTION_IDS`.
    """
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("#mw-content-text") or soup

    symbols: list[str] = []
    current_section: str | None = None
    for element in content.find_all(["h3", "tr"]):
        if element.name == "h3":
            current_section = _section_id(element)
            continue
        if current_section not in KEPT_SECTION_IDS:
            continue
        if "t-dsc" not in _css_classes(element):
            continue
        symbols.extend(_row_symbols(element))
    return symbols


def scrape_header_page(session: requests.Session, page: HeaderPage) -> tuple[HeaderPage, list[str] | FetchError]:
    """Fetch and parse one header page; return its symbols or a FetchError."""
    try:
        html = fetch(session, page.url)
    except requests.RequestException as error:
        return page, FetchError(url=page.url, reason=repr(error))
    return page, extract_symbols(html)


def _record_page_symbols(
    result: ScrapeResult,
    page: HeaderPage,
    symbols: list[str],
    wrapper_header_stems: FrozenStrSet,
) -> None:
    """Record one page's scraped `symbols` into `result`.

    Every symbol always becomes a mapping entry. When `page.stem` is a
    C-compat wrapper header (`page.stem in wrapper_header_stems`), its
    symbols are also **global names** (see CLAUDE.md, "Global name lookup")
    and get added to `result.globals_`.
    """
    is_wrapper = page.stem in wrapper_header_stems
    for symbol in symbols:
        result.add_symbol(symbol, page.header)
        if is_wrapper:
            result.globals_.add(symbol)


def scrape(
    pages: list[HeaderPage],
    *,
    workers: int = DEFAULT_WORKERS,
    wrapper_header_stems: FrozenStrSet = frozenset(),
) -> ScrapeResult:
    """Crawl `pages` concurrently and build a ScrapeResult.

    Every header contributes its own stem as a key first (CLAUDE.md: "Inject
    the header stem as a key even if tables are odd"), then its scraped
    symbols, so the stem never loses a collision to a symbol of the same
    name. `wrapper_header_stems` (from `wrapper_stems()` on the index page)
    marks which pages' symbols are also global names.
    """
    result = ScrapeResult()
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    with ThreadPoolExecutor(max_workers=workers) as executor:
        for page, outcome in executor.map(lambda p: scrape_header_page(session, p), pages):
            result.add_symbol(page.stem, page.header)
            if isinstance(outcome, FetchError):
                result.errors.append(outcome)
                continue
            _record_page_symbols(result, page, outcome, wrapper_header_stems)

    return result


def write_json(path: Path, payload: object) -> None:
    """Atomically write `payload` as pretty, sorted-key JSON to `path`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


def run_selftest() -> None:
    """Offline check of the HTML parsing logic against a fixed snippet."""
    sample_index = f"""
    <div id="mw-content-text">
      <a href="/cpp/header/vector">&lt;vector&gt;</a>
      <a href="/cpp/header/vector">&lt;vector&gt;</a>
      <a href="/cpp/header/stdatomic.h">&lt;stdatomic.h&gt;</a>
      <a href="/w/cpp/header/chrono">&lt;chrono&gt;</a>
    </div>
    """
    pages = parse_index(sample_index)
    assert [p.stem for p in pages] == ["vector"], pages

    sample_header = """
    <div id="mw-content-text">
      <h3><span class="mw-headline" id="Includes">Includes</span></h3>
      <tr class="t-dsc"><td><span class="t-lines"><span>
        <a href="/cpp/header/compare">&lt;compare&gt;</a></span></span></td></tr>
      <h3><span class="mw-headline" id="Classes">Classes</span></h3>
      <tr class="t-dsc"><td><div><span class="t-lines"><span>
        <a href="/cpp/container/vector">vector</a></span></span></div></td></tr>
      <tr class="t-dsc"><td><div><span class="t-lines"><span>
        std::hash<span class="t-dsc-small">&lt;std::vector&lt;bool&gt;&gt;</span>
      </span></span></div></td></tr>
      <h3><span class="mw-headline" id="Types">Types</span></h3>
      <tr class="t-dsc"><td><span class="t-lines">
        <span>int8_t</span><span>int16_t</span></span></td></tr>
      <tr class="t-dsc"><td><span class="t-lc">
        <a href="/cpp/chrono/duration">std::chrono::milliseconds</a></span>
        <span class="t-mark-rev t-since-cxx11">(C++11)</span></td></tr>
      <tr class="t-dsc"><td><code>true_type</code></td></tr>
      <h3><span class="mw-headline" id="Functions">Functions</span></h3>
      <tr class="t-dsc"><td><span class="t-lines"><span>
        <a href="/cpp/algorithm/fill">fill</a></span></span></td></tr>
    </div>
    """
    symbols = extract_symbols(sample_header)
    assert symbols == ["vector", "hash", "int8_t", "int16_t", "milliseconds", "true_type"], symbols

    assert _normalize_symbol("std :: chrono :: milliseconds") == "milliseconds"
    assert _normalize_symbol("vector<bool>") is None
    assert _normalize_symbol("operator+") is None

    sample_index_with_sections = f"""
    <div id="mw-content-text">
      <h2><span class="mw-headline" id="Concepts_library">Concepts library</span></h2>
      <a href="/cpp/header/vector">&lt;vector&gt;</a>
      <h2><span class="mw-headline" id="C_compatibility_headers">
        C compatibility headers</span></h2>
      <a href="/cpp/header/cstdint">&lt;cstdint&gt;</a>
      <a href="/cpp/header/climits">&lt;climits&gt;</a>
      <a href="/cpp/header/stdatomic.h">&lt;stdatomic.h&gt;</a>
      <h2><span class="mw-headline" id="Numerics_library">Numerics library</span></h2>
      <a href="/cpp/header/complex">&lt;complex&gt;</a>
    </div>
    """
    found_wrapper_stems = wrapper_stems(sample_index_with_sections)
    assert found_wrapper_stems == {"cstdint", "climits"}, found_wrapper_stems
    assert wrapper_stems("<div id=\"mw-content-text\"></div>") == set()

    wrapper_page = HeaderPage(stem="cstdint", header="<cstdint>", url="unused")
    non_wrapper_page = HeaderPage(stem="vector", header="<vector>", url="unused")

    wrapper_result = ScrapeResult()
    _record_page_symbols(
        wrapper_result, wrapper_page, ["INT_MAX", "uint32_t"], {"cstdint"}
    )
    assert wrapper_result.globals_ == {"INT_MAX", "uint32_t"}, wrapper_result.globals_
    assert wrapper_result.mappings == {"INT_MAX": "<cstdint>", "uint32_t": "<cstdint>"}

    non_wrapper_result = ScrapeResult()
    _record_page_symbols(non_wrapper_result, non_wrapper_page, ["vector"], {"cstdint"})
    assert non_wrapper_result.globals_ == set()
    assert non_wrapper_result.mappings == {"vector": "<vector>"}

    print("selftest OK")


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments for the generator CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--headers",
        nargs="+",
        metavar="STEM",
        help="Only crawl these header stems (e.g. vector chrono), skipping the index fetch.",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_MAPPINGS_PATH, help="Path to write mappings.json to.")
    parser.add_argument(
        "--workers", type=int, default=DEFAULT_WORKERS, help="Number of concurrent page fetches."
    )
    parser.add_argument(
        "--selftest", action="store_true", help="Run offline parser checks and exit, without any network access."
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    args = parse_args(sys.argv[1:] if argv is None else argv)

    if args.selftest:
        run_selftest()
        return 0

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    wrappers: set[str] = set()
    if args.headers:
        pages = [HeaderPage(stem=stem, header=f"<{stem}>", url=f"{BASE_URL}/cpp/header/{stem}") for stem in args.headers]
    else:
        index_html = fetch(session, INDEX_URL)
        pages = parse_index(index_html)
        wrappers = wrapper_stems(index_html)

    result = scrape(pages, workers=args.workers, wrapper_header_stems=wrappers)

    out_path: Path = args.out
    globals_path = out_path.parent / "globals.json"
    collisions_path = out_path.parent / "scrape-collisions.json"
    errors_path = out_path.parent / "scrape-errors.json"

    collisions_payload = {
        symbol: {"winner": result.mappings[symbol], "losers": losers} for symbol, losers in result.collisions.items()
    }

    # Per CLAUDE.md: a full crawl that finds no C-compat wrapper section is a
    # scrape error, not a silent empty globals.json — so skip the write too,
    # not just the error record, and leave any previously committed
    # globals.json alone.
    missing_wrapper_section = not args.headers and not wrappers
    if missing_wrapper_section:
        result.errors.append(
            FetchError(
                url=INDEX_URL,
                reason="C-compat wrapper headers section not found",
            )
        )

    write_json(out_path, result.mappings)
    if not missing_wrapper_section:
        write_json(globals_path, sorted(result.globals_))
    write_json(collisions_path, collisions_payload)
    write_json(errors_path, [{"url": e.url, "reason": e.reason} for e in result.errors])

    print(
        f"Crawl complete: {len(pages)} headers, {len(result.mappings)} symbols, "
        f"{len(result.globals_)} global names, {len(result.collisions)} collisions, "
        f"{len(result.errors)} errors, written to {out_path}"
    )

    return 1 if result.errors else 0


if __name__ == "__main__":
    sys.exit(main())
