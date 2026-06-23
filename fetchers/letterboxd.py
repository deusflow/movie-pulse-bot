"""Movie press RSS aggregator — collects mentions from major film publications."""

import logging

import html
import re
from typing import Dict, List

import feedparser

logger = logging.getLogger(__name__)

# Major film publication RSS feeds (all verified working).
MOVIE_FEEDS = {
    "Roger Ebert": "https://www.rogerebert.com/feed",
    "Variety": "https://variety.com/feed/",
    "Hollywood Reporter": "https://www.hollywoodreporter.com/feed/",
    "IndieWire": "https://www.indiewire.com/feed/",
}


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    return re.sub(r"<[^>]+>", "", text or "")


def _clean_text(text: str) -> str:
    """Clean and normalize text from RSS entries."""
    if not text:
        return ""
    cleaned = html.unescape(_strip_html(text)).replace("\n", " ").strip()
    # Collapse multiple spaces.
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _title_matches(entry_title: str, movie_title: str) -> bool:
    """Check if a RSS entry title mentions the movie (case-insensitive)."""
    if not entry_title or not movie_title:
        return False
    return movie_title.lower() in entry_title.lower()


def get_press_mentions(
    title: str,
    max_per_source: int = 3,
) -> Dict:
    """
    Search movie press RSS feeds for mentions of a specific movie.

    Returns dict with keys:
        mention_count: int          — total mentions across all sources
        mentions: List[Dict]        — list of mention dicts with source, headline, snippet
        sources_checked: int        — number of RSS feeds checked
        sources_with_mentions: List[str] — names of sources that mentioned the movie
    """
    mentions: List[Dict] = []
    sources_with_mentions: List[str] = []
    sources_checked = 0

    for source_name, feed_url in MOVIE_FEEDS.items():
        sources_checked += 1
        try:
            feed = feedparser.parse(feed_url)
            source_mentions = 0

            for entry in feed.entries or []:
                raw_title = entry.get("title", "")
                if not _title_matches(raw_title, title):
                    continue

                if source_mentions >= max_per_source:
                    break

                summary = entry.get("summary", "") or entry.get("description", "")
                snippet = _clean_text(summary)
                if len(snippet) > 200:
                    snippet = f"{snippet[:197]}..."

                mentions.append(
                    {
                        "source": source_name,
                        "headline": _clean_text(raw_title),
                        "snippet": snippet,
                        "link": entry.get("link", ""),
                    }
                )
                source_mentions += 1

            if source_mentions > 0:
                sources_with_mentions.append(source_name)

        except Exception as exc:
            logger.error("RSS feed failed for %s: %s", source_name, exc)
            continue

    return {
        "mention_count": len(mentions),
        "mentions": mentions,
        "sources_checked": sources_checked,
        "sources_with_mentions": sources_with_mentions,
    }


def get_all_trending_titles(limit: int = 20) -> List[Dict]:
    """
    Scan all movie press feeds and extract movie/film-related headlines.

    Returns list of dicts with keys: title, source, headline.
    Useful for cross-referencing what the press is talking about.
    """
    # Keywords that indicate a headline is about a specific movie/show.
    movie_indicators = re.compile(
        r"\b(review|box\s*office|trailer|premiere|opening|sequel|"
        r"franchise|remake|reboot|film|movie|series)\b",
        re.IGNORECASE,
    )

    items: List[Dict] = []
    seen_headlines: set = set()

    for source_name, feed_url in MOVIE_FEEDS.items():
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries or []:
                raw_title = entry.get("title", "")
                cleaned = _clean_text(raw_title)

                if not cleaned or cleaned in seen_headlines:
                    continue

                if movie_indicators.search(cleaned):
                    seen_headlines.add(cleaned)
                    items.append(
                        {
                            "headline": cleaned,
                            "source": source_name,
                        }
                    )

                if len(items) >= limit:
                    return items

        except Exception as exc:
            logger.error("RSS scan failed for %s: %s", source_name, exc)
            continue

    return items


if __name__ == "__main__":
    # Test: search for a known movie.
    print("=== Press mentions for 'Star Wars' ===")
    result = get_press_mentions("Star Wars")
    print(f"Mentions: {result['mention_count']}")
    print(f"Sources with mentions: {result['sources_with_mentions']}")
    for m in result["mentions"]:
        print(f"  [{m['source']}] {m['headline']}")

    print("\n=== Trending movie headlines ===")
    headlines = get_all_trending_titles(10)
    for h in headlines:
        print(f"  [{h['source']}] {h['headline']}")
