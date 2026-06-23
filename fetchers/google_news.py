"""Google News RSS fetcher — movie buzz measurement via news mentions."""

import logging

import html
import re
from typing import Dict, List, Optional
from urllib.parse import quote_plus

import feedparser

logger = logging.getLogger(__name__)

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    return re.sub(r"<[^>]+>", "", text or "")


def _clean_snippet(text: str) -> Optional[str]:
    """Clean and validate a news snippet."""
    if not text:
        return None
    cleaned = html.unescape(_strip_html(text)).replace("\n", " ").strip()
    if len(cleaned) < 20:
        return None
    # Trim to reasonable length.
    if len(cleaned) > 300:
        cleaned = f"{cleaned[:297]}..."
    return cleaned


def get_news_buzz(
    title: str,
    year: Optional[int] = None,
    max_snippets: int = 5,
) -> Dict:
    """
    Search Google News RSS for a movie and return buzz metrics.

    Returns dict with keys:
        mention_count: int          — total number of news articles found
        snippets: List[str]         — cleaned headline/summary snippets
        source_names: List[str]     — names of news sources
    """
    query = f"{title} movie"
    if year:
        query += f" {year}"

    url = f"{GOOGLE_NEWS_RSS}?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"

    try:
        feed = feedparser.parse(url)
        entries = feed.entries or []

        snippets: List[str] = []
        source_names: List[str] = []

        for entry in entries:
            # Extract headline as snippet.
            raw_title = entry.get("title", "")
            snippet = _clean_snippet(raw_title)
            if snippet and len(snippets) < max_snippets:
                snippets.append(snippet)

            # Extract source name.
            source = entry.get("source", {})
            source_name = source.get("title") if isinstance(source, dict) else None
            if source_name and source_name not in source_names:
                source_names.append(source_name)

        return {
            "mention_count": len(entries),
            "snippets": snippets,
            "source_names": source_names[:10],
        }

    except Exception as exc:
        logger.error("Google News RSS failed for '%s': %s", title, exc)
        return {"mention_count": 0, "snippets": [], "source_names": []}


if __name__ == "__main__":
    buzz = get_news_buzz("Sinners", 2025)
    print(f"Mentions: {buzz['mention_count']}")
    print(f"Sources: {buzz['source_names']}")
    for s in buzz["snippets"]:
        print(f"  > {s[:100]}")
