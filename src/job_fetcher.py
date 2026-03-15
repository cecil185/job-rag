"""Job posting fetcher and text extractor."""
import logging
import re
import time
from typing import Any
from typing import Optional
from urllib.parse import urlparse

import httpx
import pdfplumber
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

# Phrases that indicate the page is a block/error page (Cloudflare, cookie wall, etc.), not job content.
_BLOCK_PAGE_PHRASES = (
    "you have been blocked",
    "you are unable to access",
    "why have i been blocked",
    "security service to protect itself",
    "performance & security by cloudflare",
    "sorry, you have been blocked",
    "enable javascript",
    "checking your browser",
    "access denied",
    "blocked by",
)


def looks_like_block_or_error_page(text: str) -> bool:
    """
    Return True if the text looks like a block/error page (e.g. Cloudflare, cookie wall)
    rather than a job posting.
    """
    if not text or not text.strip():
        return False
    lower = text.strip().lower()
    # Use first ~3k chars to avoid scanning huge pastes; block pages are short.
    sample = lower[:3000] if len(lower) > 3000 else lower
    return any(phrase in sample for phrase in _BLOCK_PAGE_PHRASES)


class JobFetcher:
    """Fetches and extracts text from job postings."""

    def __init__(self) -> None:
        self.playwright: Any = None
        self.browser: Any = None

    def __enter__(self) -> "JobFetcher":
        t0 = time.perf_counter()
        logger.info("JobFetcher: starting Playwright browser")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        logger.info("JobFetcher: browser ready in %.2fs", time.perf_counter() - t0)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def fetch(self, url: str) -> dict[str, Any]:
        """
        Fetch job posting from URL.

        Returns:
            Dict with 'text', 'metadata'
        """
        t0 = time.perf_counter()
        parsed = urlparse(url)

        # Handle PDFs
        if url.lower().endswith('.pdf') or 'pdf' in parsed.path.lower():
            out = self._fetch_pdf(url)
            logger.info("fetch: PDF url=%s done in %.2fs", url[:50], time.perf_counter() - t0)
            return out

        # Handle web pages
        out = self._fetch_web(url)
        logger.info("fetch: web url=%s done in %.2fs", url[:50], time.perf_counter() - t0)
        return out

    def _fetch_pdf(self, url: str) -> dict[str, Any]:
        """Extract text from PDF."""
        try:
            response = httpx.get(url, timeout=30.0)
            response.raise_for_status()

            with pdfplumber.open(response.content) as pdf:
                text_parts = []
                for page in pdf.pages:
                    text_parts.append(page.extract_text() or "")

                full_text = "\n\n".join(text_parts)
                return {
                    "text": full_text,
                    "metadata": {"source": "pdf", "url": url}
                }
        except Exception as e:
            raise RuntimeError(f"Failed to fetch PDF: {e}") from e

    def _fetch_web(self, url: str) -> dict[str, Any]:
        """Extract text from web page."""
        try:
            t0 = time.perf_counter()
            if self.browser is None:
                raise RuntimeError("Browser not initialized")
            page = self.browser.new_page()
            logger.info("_fetch_web: navigating to %s", url[:50])
            page.goto(url, wait_until="networkidle", timeout=30000)
            logger.info("_fetch_web: page loaded in %.2fs", time.perf_counter() - t0)

            # Get page content
            html = page.content()
            soup = BeautifulSoup(html, 'lxml')

            # Remove script and style elements
            for script in soup(["script", "style", "nav", "header", "footer"]):
                script.decompose()

            # Try to find main content area
            main_content = (
                soup.find('main') or
                soup.find('article') or
                soup.find(class_=re.compile(r'content|description|job|posting', re.I)) or
                soup.find(id=re.compile(r'content|description|job|posting', re.I)) or
                soup.body
            )

            if main_content:
                text = main_content.get_text(separator='\n', strip=True)
            else:
                text = soup.get_text(separator='\n', strip=True)

            # Clean up text
            text = re.sub(r'\n{3,}', '\n\n', text)

            if looks_like_block_or_error_page(text):
                page.close()
                raise Exception(
                    "Page content appears to be a block or error page (e.g. Cloudflare), not a job posting. "
                    "Use the 'Could not extract' tab to paste the job text."
                )

            page.close()
            return {
                "text": text,
                "metadata": {"source": "web", "url": url}
            }
        except Exception as e:
            raise RuntimeError(f"Failed to fetch web page: {e}") from e
