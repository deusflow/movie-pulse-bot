"""Discovery module — scans multiple sources to find what people are discussing TODAY.

This is the FIRST step in the pipeline. Instead of picking films from TMDB
trending and then looking for discussions, we scan discussions FIRST and let
AI decide what's the hottest content.

Sources (in priority order):
    1. Reddit hot posts (r/movies, r/television, r/boxoffice, etc.)
    2. Google News RSS (movie/TV headlines today)
    3. Press RSS (Variety, Hollywood Reporter, IndieWire, Roger Ebert)
    4. YouTube trending trailers & discussions
    5. TMDB trending (supplementary signal, not the primary source)
"""

import logging
import re
from typing import Dict, List, Optional
from urllib.parse import quote_plus

import feedparser
import requests

from fetchers.reddit import get_reddit_trending, _MOVIE_SUBS, _TV_SUBS
from fetchers.letterboxd import get_all_trending_titles
from fetchers.tmdb import get_trending_all

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Google News — general movie/TV news scan
# ---------------------------------------------------------------------------
_NEWS_QUERIES = [
    "new movies 2026",
    "trending movies today",
    "new TV series 2026",
    "trending series today",
    "box office this week",
]

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


def _scan_google_news(max_per_query: int = 8) -> List[Dict]:
    """Scan Google News RSS for movie/TV-related headlines."""
    items: List[Dict] = []
    seen: set = set()

    for query in _NEWS_QUERIES:
        try:
            url = f"{GOOGLE_NEWS_RSS}?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(url)
            for entry in (feed.entries or [])[:max_per_query]:
                headline = entry.get("title", "").strip()
                if not headline or headline in seen:
                    continue
                seen.add(headline)
                items.append({
                    "title_raw": headline,
                    "source": "google_news",
                    "context": headline,
                })
        except Exception as exc:
            logger.warning("Google News scan failed for '%s': %s", query, exc)

    logger.info("📰 Google News: %d headlines collected", len(items))
    return items


# ---------------------------------------------------------------------------
# YouTube — trending movie/TV content
# ---------------------------------------------------------------------------
import os
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
YT_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

_YT_QUERIES = [
    "new movie trailer 2026",
    "new series trailer 2026",
    "movie review today",
    "TV show discussion",
]


def _scan_youtube(max_per_query: int = 5) -> List[Dict]:
    """Search YouTube for trending movie/TV content."""
    if not YOUTUBE_API_KEY:
        logger.info("YOUTUBE_API_KEY missing — skipping YouTube scan")
        return []

    items: List[Dict] = []
    seen: set = set()

    for query in _YT_QUERIES:
        try:
            response = requests.get(
                YT_SEARCH_URL,
                params={
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "maxResults": max_per_query,
                    "order": "date",
                    "publishedAfter": _get_today_iso(),
                    "key": YOUTUBE_API_KEY,
                },
                timeout=10,
            )
            if response.status_code != 200:
                logger.warning("YouTube search failed (%d) for '%s'", response.status_code, query)
                continue

            data = response.json()
            for item in data.get("items", []):
                title = item.get("snippet", {}).get("title", "")
                if not title or title in seen:
                    continue
                seen.add(title)
                items.append({
                    "title_raw": title,
                    "source": "youtube",
                    "context": title,
                })
        except Exception as exc:
            logger.warning("YouTube scan failed for '%s': %s", query, exc)

    logger.info("🎥 YouTube: %d videos collected", len(items))
    return items


def _get_today_iso() -> str:
    """Return today's date at midnight in ISO 8601 format for YouTube API."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT00:00:00Z")


# ---------------------------------------------------------------------------
# Reddit — hot posts scan
# ---------------------------------------------------------------------------
def _scan_reddit() -> List[Dict]:
    """Scan Reddit hot posts from movie/TV subreddits."""
    items: List[Dict] = []

    # Movie subreddits
    movie_posts = get_reddit_trending(media_type="movie", limit=15)
    for post in movie_posts:
        items.append({
            "title_raw": post.get("title", ""),
            "source": f"reddit/r/{post.get('subreddit', '')}",
            "context": post.get("title", ""),
            "media_hint": "movie",
        })

    # TV subreddits
    tv_posts = get_reddit_trending(media_type="tv", limit=15)
    for post in tv_posts:
        items.append({
            "title_raw": post.get("title", ""),
            "source": f"reddit/r/{post.get('subreddit', '')}",
            "context": post.get("title", ""),
            "media_hint": "tv",
        })

    logger.info("💬 Reddit: %d hot posts collected", len(items))
    return items


# ---------------------------------------------------------------------------
# Press RSS — movie publication headlines
# ---------------------------------------------------------------------------
def _scan_press() -> List[Dict]:
    """Scan major film publication RSS feeds for trending headlines."""
    items: List[Dict] = []

    headlines = get_all_trending_titles(limit=20)
    for h in headlines:
        items.append({
            "title_raw": h.get("headline", ""),
            "source": f"press/{h.get('source', '')}",
            "context": h.get("headline", ""),
        })

    logger.info("📝 Press RSS: %d headlines collected", len(items))
    return items


# ---------------------------------------------------------------------------
# TMDB — trending as supplementary signal
# ---------------------------------------------------------------------------
def _scan_tmdb() -> List[Dict]:
    """Get TMDB trending as supplementary signal (not primary source)."""
    items: List[Dict] = []

    trending = get_trending_all(limit=20)
    for t in trending:
        title = t.get("title") or t.get("name", "")
        media_type = t.get("media_type", "movie")
        popularity = t.get("popularity", 0)
        items.append({
            "title_raw": title,
            "source": "tmdb_trending",
            "context": f"{title} (TMDB popularity: {popularity:.0f})",
            "media_hint": media_type,
            "tmdb_id": t.get("id"),
            "tmdb_data": t,  # Keep full TMDB data for later enrichment
        })

    logger.info("🎬 TMDB: %d trending items collected", len(items))
    return items


# ---------------------------------------------------------------------------
# Main aggregator
# ---------------------------------------------------------------------------
def discover_discussions() -> List[Dict]:
    """
    Scan ALL sources and return a unified list of discussions/mentions.

    Each item has:
        title_raw: str      — raw headline/title from the source
        source: str         — source identifier (reddit, youtube, etc.)
        context: str        — full context text for AI
        media_hint: str     — optional "movie" or "tv" hint
        tmdb_id: int        — optional, if from TMDB
        tmdb_data: Dict     — optional, full TMDB item

    Returns list of 30-80 discussion items from all sources.
    """
    logger.info("🔍 Starting multi-source discussion scan...")

    all_items: List[Dict] = []

    # 1. Reddit — highest priority (real audience discussion)
    all_items.extend(_scan_reddit())

    # 2. Google News — what media is writing about
    all_items.extend(_scan_google_news())

    # 3. Press RSS — film critic publications
    all_items.extend(_scan_press())

    # 4. YouTube — trailer reactions and discussions
    all_items.extend(_scan_youtube())

    # 5. TMDB trending — supplementary algorithmic signal
    all_items.extend(_scan_tmdb())

    logger.info(
        "✅ Discovery complete: %d total items from %d sources",
        len(all_items),
        len(set(item["source"].split("/")[0] for item in all_items)),
    )

    return all_items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    items = discover_discussions()
    print(f"\n=== Found {len(items)} discussion items ===")
    for i, item in enumerate(items[:20], 1):
        print(f"  {i}. [{item['source']}] {item['title_raw'][:80]}")
