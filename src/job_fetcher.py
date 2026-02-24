"""Job posting fetcher and text extractor."""
import httpx
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pdfplumber
from typing import Dict, Optional
from urllib.parse import urlparse
import re


class JobFetcher:
    """Fetches and extracts text from job postings."""
    
    def __init__(self):
        self.playwright = None
        self.browser = None
    
    def __enter__(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
    
    def fetch(self, url: str) -> Dict[str, Optional[str]]:
        """
        Fetch job posting from URL.
        
        Returns:
            Dict with 'text', 'title', 'metadata'
        """
        parsed = urlparse(url)
        
        # Handle PDFs
        if url.lower().endswith('.pdf') or 'pdf' in parsed.path.lower():
            return self._fetch_pdf(url)
        
        # Handle web pages
        return self._fetch_web(url)
    
    def _fetch_pdf(self, url: str) -> Dict[str, Optional[str]]:
        """Extract text from PDF."""
        try:
            response = httpx.get(url, timeout=30.0)
            response.raise_for_status()
            
            with pdfplumber.open(response.content) as pdf:
                text_parts = []
                for page in pdf.pages:
                    text_parts.append(page.extract_text() or "")
                
                full_text = "\n\n".join(text_parts)
                title = self._extract_title_from_text(full_text)
                return {
                    "text": full_text,
                    "title": title,
                    "metadata": {"source": "pdf", "url": url}
                }
        except Exception as e:
            raise Exception(f"Failed to fetch PDF: {e}")
    
    def _fetch_web(self, url: str) -> Dict[str, Optional[str]]:
        """Extract text from web page."""
        try:
            page = self.browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            
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
            
            title = self._extract_title_from_page(soup, page)
            page.close()
            return {
                "text": text,
                "title": title,
                "metadata": {"source": "web", "url": url}
            }
        except Exception as e:
            raise Exception(f"Failed to fetch web page: {e}")
    
    def _extract_title_from_page(self, soup: BeautifulSoup, page) -> Optional[str]:
        """Extract job title from page."""
        title = None
        title_selectors = [
            'h1',
            '[class*="title"]',
            '[class*="job-title"]',
            '[id*="title"]',
            'title'
        ]
        for selector in title_selectors:
            elem = soup.select_one(selector)
            if elem:
                title = elem.get_text(strip=True)
                if title and len(title) < 200:
                    break
        if not title:
            page_title = page.title()
            if page_title:
                title = page_title.split('|')[0].split('-')[0].strip()
        return title

    def _extract_title_from_text(self, text: str) -> Optional[str]:
        """Extract job title from text content (e.g. PDF)."""
        lines = text.split('\n')[:20]
        for line in lines:
            line = line.strip()
            if not line or len(line) >= 100:
                continue
            if any(word in line.lower() for word in ['engineer', 'developer', 'manager', 'analyst', 'specialist']):
                return line
        return None
