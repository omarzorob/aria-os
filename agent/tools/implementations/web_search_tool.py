"""
P1-21: Web Search Tool

Provides web search functionality using Brave Search API (primary)
or DuckDuckGo scraping (fallback). Returns structured result lists.

Environment variables:
- BRAVE_API_KEY: Brave Search API key (get at https://brave.com/search/api/)
  If not set, falls back to DuckDuckGo scraping.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
DDG_SEARCH_URL = "https://html.duckduckgo.com/html/"
DEFAULT_COUNT = 5


@dataclass
class SearchResult:
    """Represents a single web search result."""

    title: str
    url: str
    snippet: str
    published_date: str = ""
    source: str = ""

    def __str__(self) -> str:
        return f"{self.title}\n{self.url}\n{self.snippet}"


class WebSearchTool:
    """
    Web search tool using Brave Search API or DuckDuckGo fallback.

    Usage:
        search = WebSearchTool()
        results = search.search("Python asyncio tutorial")
        summary = search.search_and_summarize("latest AI news")
    """

    def __init__(self, brave_api_key: Optional[str] = None) -> None:
        """
        Initialize the WebSearchTool.

        Args:
            brave_api_key: Brave API key. Falls back to BRAVE_API_KEY env var.
        """
        self.brave_api_key = brave_api_key or os.environ.get("BRAVE_API_KEY", "")

    def search(
        self,
        query: str,
        count: int = DEFAULT_COUNT,
        country: str = "US",
        freshness: Optional[str] = None,
    ) -> list[SearchResult]:
        """
        Search the web for the given query.

        Args:
            query: Search query string.
            count: Number of results to return (max 10 for Brave).
            country: Country code for localized results (e.g., "US", "GB").
            freshness: Optional freshness filter ("pd"=past day, "pw"=past week,
                       "pm"=past month, "py"=past year).

        Returns:
            List of SearchResult objects.
        """
        if self.brave_api_key:
            try:
                return self._brave_search(query, count, country, freshness)
            except Exception as e:
                logger.warning("Brave Search failed, falling back to DDG: %s", e)

        return self._ddg_search(query, count)

    def search_and_summarize(
        self,
        query: str,
        count: int = 5,
    ) -> str:
        """
        Search the web and return a summarized text of the top results.

        Args:
            query: Search query.
            count: Number of results to include in summary.

        Returns:
            Formatted string summary of top search results.
        """
        results = self.search(query, count=count)

        if not results:
            return f"No results found for: {query}"

        lines = [f"Search results for: '{query}'\n"]
        for i, result in enumerate(results, 1):
            lines.append(f"{i}. **{result.title}**")
            lines.append(f"   {result.url}")
            if result.snippet:
                lines.append(f"   {result.snippet[:300]}")
            lines.append("")

        return "\n".join(lines)

    def news_search(self, query: str, count: int = 5) -> list[SearchResult]:
        """
        Search for recent news articles.

        Args:
            query: News search query.
            count: Number of results.

        Returns:
            List of SearchResult objects from news sources.
        """
        if self.brave_api_key:
            try:
                return self._brave_news_search(query, count)
            except Exception as e:
                logger.warning("Brave News failed: %s", e)

        # Fallback: regular search with news-biased query
        return self.search(f"{query} news", count=count, freshness="pw")

    # ------------------------------------------------------------------
    # Brave Search API
    # ------------------------------------------------------------------

    def _brave_search(
        self,
        query: str,
        count: int,
        country: str,
        freshness: Optional[str],
    ) -> list[SearchResult]:
        """Execute search via Brave Search API."""
        params: dict[str, str] = {
            "q": query,
            "count": str(min(count, 10)),
            "country": country,
            "search_lang": "en",
        }
        if freshness:
            params["freshness"] = freshness

        url = BRAVE_SEARCH_URL + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": self.brave_api_key,
            },
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())

        results: list[SearchResult] = []
        for item in data.get("web", {}).get("results", []):
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("description", ""),
                published_date=item.get("age", ""),
                source=item.get("meta_url", {}).get("netloc", ""),
            ))

        return results

    def _brave_news_search(self, query: str, count: int) -> list[SearchResult]:
        """Execute news search via Brave Search API."""
        params = {
            "q": query,
            "count": str(min(count, 10)),
            "freshness": "pw",
        }
        url = BRAVE_SEARCH_URL + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": self.brave_api_key,
            },
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())

        results: list[SearchResult] = []
        for item in data.get("news", {}).get("results", []):
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("description", ""),
                published_date=item.get("age", ""),
                source=item.get("meta_url", {}).get("netloc", ""),
            ))

        return results

    # ------------------------------------------------------------------
    # DuckDuckGo fallback
    # ------------------------------------------------------------------

    def _ddg_search(self, query: str, count: int) -> list[SearchResult]:
        """
        Scrape DuckDuckGo HTML search results as a fallback.

        Note: This is a best-effort scraper and may break if DDG changes
        their HTML layout.
        """
        params = {"q": query, "kl": "us-en", "kp": "-1"}
        url = DDG_SEARCH_URL + "?" + urllib.parse.urlencode(params)

        req = urllib.request.Request(
            url,
            data=urllib.parse.urlencode(params).encode(),
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Linux; Android 13) "
                    "AppleWebKit/537.36 Chrome/116.0 Safari/537.36"
                ),
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode("utf-8", errors="replace")
        except Exception as e:
            logger.error("DuckDuckGo search failed: %s", e)
            return []

        return self._parse_ddg_html(html, count)

    def _parse_ddg_html(self, html: str, count: int) -> list[SearchResult]:
        """Parse DuckDuckGo HTML results page."""
        results: list[SearchResult] = []

        # Extract result blocks
        result_pattern = re.compile(
            r'class="result__title"[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>'
            r'.*?class="result__snippet"[^>]*>(.*?)</div>',
            re.DOTALL | re.IGNORECASE,
        )

        for match in result_pattern.finditer(html):
            if len(results) >= count:
                break
            url = match.group(1)
            title = re.sub(r"<[^>]+>", "", match.group(2)).strip()
            snippet = re.sub(r"<[^>]+>", "", match.group(3)).strip()

            # Clean DDG redirect URLs
            if "uddg=" in url:
                url_match = re.search(r"uddg=([^&]+)", url)
                if url_match:
                    url = urllib.parse.unquote(url_match.group(1))

            if title and url:
                results.append(SearchResult(title=title, url=url, snippet=snippet))

        return results
