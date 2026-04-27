"""Deterministic Web Scraper — reliable HTML extraction for agent intelligence.

Inspired by Santiago Valdarrama / Apify: "At 100 pages, your agent will
start making decisions based on data that's wrong in ways you can't even
detect."  The solution is deterministic extraction + LLM analysis — never
let the LLM parse raw HTML.

Architecture:
  1. Fetch page (requests + SSRF guard)
  2. Parse deterministically (BeautifulSoup)
  3. Extract structured data (title, text, links, meta, tables)
  4. Return clean dict for LLM analysis

This module is designed for the CollectorHand and any agent subsystem
that needs reliable web intelligence.
"""

import logging
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Optional
from urllib.parse import urljoin, urlparse

_log = logging.getLogger("scraper")

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ScrapedPage:
    """Deterministically extracted page content."""
    url: str
    title: str = ""
    description: str = ""
    author: str = ""
    published_date: str = ""
    text_content: str = ""           # main body text, cleaned
    headings: list[str] = field(default_factory=list)
    links: list[dict] = field(default_factory=list)   # [{text, href}]
    images: list[dict] = field(default_factory=list)   # [{alt, src}]
    tables: list[list[list[str]]] = field(default_factory=list)  # list of tables
    meta: dict = field(default_factory=dict)
    word_count: int = 0
    fetch_time: float = 0.0
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self, max_text: int = 2000) -> dict:
        """Return a compact summary suitable for LLM context injection."""
        return {
            "url": self.url,
            "title": self.title,
            "description": self.description,
            "word_count": self.word_count,
            "headings": self.headings[:20],
            "text": self.text_content[:max_text],
            "link_count": len(self.links),
            "table_count": len(self.tables),
        }


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

# Tags whose text content is not useful
_SKIP_TAGS = frozenset([
    "script", "style", "noscript", "svg", "path", "meta", "link",
    "head", "iframe", "object", "embed",
])

# Common boilerplate selectors to remove
_BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", ".sidebar", "#sidebar",
    ".nav", ".menu", ".cookie", ".banner", ".ad", ".advertisement",
    "[role='navigation']", "[role='banner']", "[role='contentinfo']",
]


class WebScraper:
    """Deterministic web scraper with SSRF protection."""

    def __init__(self, timeout: float = 15.0, max_content_length: int = 5_000_000):
        self.timeout = timeout
        self.max_content_length = max_content_length
        self._session: Optional[object] = None

    def _get_session(self):
        if not _HAS_REQUESTS:
            raise RuntimeError("requests library not installed")
        if self._session is None:
            self._session = _requests.Session()
            self._session.headers.update({
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            })
        return self._session

    def scrape(self, url: str) -> ScrapedPage:
        """Fetch and deterministically extract content from a URL.

        Returns a ScrapedPage with all fields populated.
        Applies SSRF protection via core.url_guard before fetching.
        """
        page = ScrapedPage(url=url)
        start = time.time()

        # SSRF protection
        try:
            from core.url_guard import check_url
            verdict = check_url(url)
            if not verdict.allowed:
                page.error = f"SSRF blocked: {verdict.reason}"
                _log.warning(f"Scrape blocked by URL guard: {url} — {verdict.reason}")
                return page
        except ImportError:
            pass  # url_guard not available, proceed with caution

        if not _HAS_REQUESTS:
            page.error = "requests library not installed"
            return page
        if not _HAS_BS4:
            page.error = "beautifulsoup4 library not installed"
            return page

        # Fetch
        try:
            session = self._get_session()
            resp = session.get(
                url, timeout=self.timeout,
                stream=True, allow_redirects=True,
            )
            resp.raise_for_status()

            # Check content length
            content_length = int(resp.headers.get("content-length", 0))
            if content_length > self.max_content_length:
                page.error = f"Content too large: {content_length} bytes"
                return page

            # Only process HTML
            content_type = resp.headers.get("content-type", "")
            if "html" not in content_type.lower() and "xml" not in content_type.lower():
                page.error = f"Not HTML: {content_type}"
                return page

            html = resp.text[:self.max_content_length]

        except _requests.RequestException as e:
            page.error = f"Fetch failed: {e}"
            _log.warning(f"Scrape fetch error for {url}: {e}")
            return page

        # Parse
        try:
            page = self._parse_html(html, url, page)
        except Exception as e:
            page.error = f"Parse failed: {e}"
            _log.warning(f"Scrape parse error for {url}: {e}")

        page.fetch_time = round(time.time() - start, 2)
        return page

    def _parse_html(self, html: str, url: str, page: ScrapedPage) -> ScrapedPage:
        """Deterministically extract structured data from HTML."""
        soup = BeautifulSoup(html, "html.parser")

        # Title
        title_tag = soup.find("title")
        page.title = title_tag.get_text(strip=True) if title_tag else ""

        # Meta tags
        page.meta = self._extract_meta(soup)
        page.description = page.meta.get("description", "")
        page.author = page.meta.get("author", "")
        page.published_date = page.meta.get("article:published_time",
                                             page.meta.get("date", ""))

        # Remove boilerplate
        for selector in _BOILERPLATE_SELECTORS:
            for tag in soup.select(selector):
                tag.decompose()

        # Remove script/style/etc
        for tag in soup.find_all(_SKIP_TAGS):
            tag.decompose()

        # Headings
        for level in range(1, 5):
            for h in soup.find_all(f"h{level}"):
                text = h.get_text(strip=True)
                if text:
                    page.headings.append(f"H{level}: {text}")

        # Main text content
        # Try to find the main content area
        main = (soup.find("main") or soup.find("article")
                or soup.find(id="content") or soup.find(class_="content")
                or soup.find("body") or soup)

        paragraphs = []
        for p in main.find_all(["p", "li", "blockquote", "pre", "td"]):
            text = p.get_text(separator=" ", strip=True)
            if text and len(text) > 20:
                paragraphs.append(text)

        page.text_content = "\n\n".join(paragraphs)
        page.word_count = len(page.text_content.split())

        # Links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith(("#", "javascript:", "mailto:")):
                continue
            abs_href = urljoin(url, href)
            link_text = a.get_text(strip=True)
            if link_text:
                page.links.append({"text": link_text[:100], "href": abs_href})

        # Cap links
        page.links = page.links[:50]

        # Images
        for img in soup.find_all("img", src=True):
            page.images.append({
                "alt": img.get("alt", "")[:100],
                "src": urljoin(url, img["src"]),
            })
        page.images = page.images[:20]

        # Tables
        for table in soup.find_all("table"):
            rows = []
            for tr in table.find_all("tr"):
                cells = []
                for td in tr.find_all(["td", "th"]):
                    cells.append(td.get_text(strip=True)[:200])
                if cells:
                    rows.append(cells)
            if rows:
                page.tables.append(rows)
        page.tables = page.tables[:5]

        return page

    @staticmethod
    def _extract_meta(soup) -> dict:
        """Extract all meta tag content into a flat dict."""
        meta = {}
        for tag in soup.find_all("meta"):
            name = (tag.get("name") or tag.get("property")
                    or tag.get("itemprop") or "").lower()
            content = tag.get("content", "")
            if name and content:
                meta[name] = content[:500]
        return meta

    def scrape_multiple(self, urls: list[str]) -> list[ScrapedPage]:
        """Scrape multiple URLs sequentially."""
        results = []
        for url in urls:
            results.append(self.scrape(url))
        return results


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------

def scrape_url(url: str) -> ScrapedPage:
    """One-shot scrape a single URL."""
    return WebScraper().scrape(url)


def scrape_for_llm(url: str, max_text: int = 3000) -> dict:
    """Scrape a URL and return a compact dict ready for LLM context."""
    page = scrape_url(url)
    if page.error:
        return {"url": url, "error": page.error}
    return page.summary(max_text=max_text)
