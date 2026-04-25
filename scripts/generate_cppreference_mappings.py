#!/usr/bin/env python3
"""Generate `res/mappings.json` from cppreference C++ header pages.

The script uses Crawlee's `BeautifulSoupCrawler` so the crawl has retry logic,
request handling timeouts, and a consistent request lifecycle. It first crawls
https://en.cppreference.com/cpp/header to collect header page URLs, then visits
those header pages and extracts symbol names from section tables.

Output format:
- JSON object
- key: symbol name visible on cppreference, for example `vector` or `operator new`
- value: header name in angle-bracket form, for example `<vector>`
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup
from crawlee import ConcurrencySettings, Request
from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext

BASE_URL = 'https://en.cppreference.com'
HEADER_INDEX_URL = f'{BASE_URL}/cpp/header'
HEADER_LINK_RE = re.compile(r'^/(?:w/)?(?:cpp|c)/header/[^/#?]+$')
SYMBOL_LINK_RE = re.compile(r'^/w/(?:cpp|c)/(?!header/).+')
INDEX_PATHS = {'/cpp/header', '/cpp/header/'}
DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parents[1] / 'res' / 'mappings.json'


@dataclass
class CrawlState:
    """Mutable state shared across crawler handlers."""

    header_requests: list[Request] = field(default_factory=list)
    symbol_to_header: dict[str, str] = field(default_factory=dict)
    collisions: dict[str, set[str]] = field(default_factory=dict)
    failed_requests: list[tuple[str, str]] = field(default_factory=list)
    discovered_headers: set[str] = field(default_factory=set)


STATE = CrawlState()


def is_header_link(href: str | None) -> bool:
    """Return True when href points to a cppreference header page.

    The index page contains many links, but we only care about header pages.
    This keeps the crawl focused and prevents accidental traversal of unrelated
    pages.
    """

    if not href:
        return False

    parsed = urlparse(urljoin(BASE_URL, href))
    return bool(HEADER_LINK_RE.fullmatch(parsed.path.rstrip('/')))


def is_symbol_link(href: str | None) -> bool:
    """Return True when href points to a cppreference symbol documentation page."""

    if not href or href.startswith('#'):
        return False

    parsed = urlparse(urljoin(BASE_URL, href))
    path = parsed.path.rstrip('/')

    if not path or is_header_link(href):
        return False

    return bool(SYMBOL_LINK_RE.match(path))


def normalize_header_name(raw_text: str, href: str) -> str:
    """Normalize a header label to angle-bracket form.

    cppreference usually renders header labels as `<vector>` or `<stdatomic.h>`.
    When extra annotations appear, the first token still contains the canonical
    header name, so we strip annotations but preserve the angle brackets.
    """

    text = raw_text.strip()
    if not text:
        text = unquote(urlparse(urljoin(BASE_URL, href)).path.rstrip('/').split('/')[-1])

    # Keep only the visible header token, for example `<vector>` from
    # `<vector> (C++20)`.
    token = text.split()[0]
    match = re.search(r'<[^>]+>', token)
    if match:
        return match.group(0)

    if token.startswith('<') and token.endswith('>'):
        return token

    return f'<{token.strip("<>")}>'


def canonical_header_name_from_request(request_url: str, user_data: Any) -> str:
    """Read canonical header name from request metadata, with URL fallback."""

    if isinstance(user_data, dict):
        header_name = user_data.get('header_name')
        if isinstance(header_name, str) and header_name:
            return header_name

    segment = unquote(urlparse(request_url).path.rstrip('/').split('/')[-1])
    return f'<{segment}>' if segment else request_url


def normalize_symbol_name(text: str) -> str:
    """Collapse whitespace around symbol text while preserving the symbol itself."""

    return re.sub(r'\s+', ' ', text).strip()


def extract_index_headers(soup: BeautifulSoup) -> list[Request]:
    """Extract header-page requests from the cppreference header index.

    The index page may contain repeated links to the same header in explanatory
    text, so we deduplicate by canonical header name and keep the first occurrence
    to preserve stable ordering.
    """

    container = soup.select_one('#mw-content-text') or soup.body or soup
    seen_headers: set[str] = set()
    header_requests: list[Request] = []

    for anchor in container.find_all('a', href=True):
        href = anchor.get('href', '')
        if not is_header_link(href):
            continue

        canonical_name = normalize_header_name(anchor.get_text(' ', strip=True), href)
        if canonical_name in seen_headers:
            continue

        seen_headers.add(canonical_name)
        request_url = urljoin(BASE_URL, href)
        header_requests.append(Request.from_url(request_url, user_data={'header_name': canonical_name}))

    return header_requests


def extract_symbols_from_header_page(soup: BeautifulSoup) -> list[str]:
    """Collect symbol names listed in the page section tables.

    cppreference header pages are table-driven. We walk table rows, look at the
    first table cell, and gather any non-header links inside it. Rows whose first
    cell contains another header link are skipped, because those rows represent
    included headers rather than symbols defined or documented in the current
    header page.
    """

    container = soup.select_one('#mw-content-text') or soup.body or soup
    symbols: list[str] = []
    seen: set[str] = set()

    for row in container.find_all('tr'):
        cells = row.find_all('td', recursive=False)
        if not cells:
            continue

        first_cell = cells[0]
        if first_cell.find('td') is not None:
            # Defensive guard for malformed nested tables.
            continue

        anchors = [anchor for anchor in first_cell.find_all('a', href=True) if is_symbol_link(anchor.get('href'))]
        if not anchors:
            continue

        candidate_texts = [normalize_symbol_name(anchor.get_text(' ', strip=True)) for anchor in anchors]

        for candidate in candidate_texts:
            if not candidate or candidate in seen:
                continue

            seen.add(candidate)
            symbols.append(candidate)

    return symbols


async def process_index_page(context: BeautifulSoupCrawlingContext) -> None:
    """Handle the header index page by queueing header pages discovered there."""

    STATE.header_requests = extract_index_headers(context.soup)
    STATE.discovered_headers = {request.user_data['header_name'] for request in STATE.header_requests}  # type: ignore[index]

    context.log.info(f'Discovered {len(STATE.header_requests)} header pages from index.')
    await context.add_requests(STATE.header_requests)


async def process_header_page(context: BeautifulSoupCrawlingContext) -> None:
    """Handle a single header page and record every symbol found on it."""

    header_name = canonical_header_name_from_request(context.request.url, context.request.user_data)
    symbols = extract_symbols_from_header_page(context.soup)

    context.log.info(f'Extracted {len(symbols)} symbols from {header_name}.')

    for symbol in symbols:
        existing_header = STATE.symbol_to_header.get(symbol)
        if existing_header is None:
            STATE.symbol_to_header[symbol] = header_name
            continue

        if existing_header == header_name:
            continue

        # Deterministic policy: first header wins. Keep a collision log so we can
        # inspect symbols that show up in multiple headers.
        STATE.collisions.setdefault(symbol, {existing_header}).add(header_name)


async def build_mappings(output_path: Path) -> None:
    """Run the crawl and write the final JSON mapping to disk."""

    crawler = BeautifulSoupCrawler(
        # Rate-limit the crawl to keep the run polite and stable.
        concurrency_settings=ConcurrencySettings(desired_concurrency=10, max_concurrency=20, max_tasks_per_minute=180),
        max_request_retries=3,
        max_requests_per_crawl=2000,
        request_handler_timeout=timedelta(seconds=90),
        respect_robots_txt_file=False,
    )

    @crawler.router.default_handler
    async def default_handler(context: BeautifulSoupCrawlingContext) -> None:
        path = urlparse(context.request.url).path.rstrip('/')
        if path in INDEX_PATHS:
            await process_index_page(context)
        else:
            await process_header_page(context)

    @crawler.failed_request_handler
    async def failed_handler(context: Any, error: Exception) -> None:
        url = getattr(getattr(context, 'request', None), 'url', '<unknown>')
        STATE.failed_requests.append((url, repr(error)))
        context.log.error(f'Failed request after retries: {url} -> {error!r}')

    await crawler.run([HEADER_INDEX_URL])

    if STATE.failed_requests:
        failed_urls = '\n'.join(f' - {url}: {error}' for url, error in STATE.failed_requests)
        raise RuntimeError(f'Crawl failed for some requests; mappings file will not be written:\n{failed_urls}')

    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(STATE.symbol_to_header, ensure_ascii=False, indent=2, sort_keys=True) + '\n'

    temp_path = output_path.with_suffix(output_path.suffix + '.tmp')
    temp_path.write_text(payload, encoding='utf-8')
    temp_path.replace(output_path)

    print(
        'Crawl complete: '
        f'{len(STATE.header_requests)} headers, '
        f'{len(STATE.symbol_to_header)} symbols, '
        f'{len(STATE.collisions)} collisions, '
        f'written to {output_path}'
    )


async def main() -> None:
    """Entry point used by the command line wrapper."""

    await build_mappings(DEFAULT_OUTPUT_PATH)


if __name__ == '__main__':
    asyncio.run(main())
