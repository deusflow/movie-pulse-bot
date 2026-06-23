"""Reddit discussions fetcher — RSS-only strategy.

Reddit blocks all JSON/API access with 403. However, RSS feeds work
reliably for both post discovery and comment retrieval:

    - Search: www.reddit.com/r/{sub}/search.rss?q={query}
    - Hot:    www.reddit.com/r/{sub}/hot.rss
    - Comments: www.reddit.com/comments/{post_id}/.rss

No API keys needed. No browser dependencies. Works perfectly on GitHub Actions.
"""

import html
import logging
import random
import re
import time
from typing import Dict, List, Optional
from urllib.parse import quote_plus

import feedparser

logger = logging.getLogger(__name__)

# Subreddits for movies and TV discussion.
_MOVIE_SUBS = ("movies", "boxoffice", "TrueFilm", "Letterboxd")
_TV_SUBS = ("television", "tvplus", "netflixbestof")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _clean(text: str) -> Optional[str]:
    """Clean an RSS comment/body, stripping HTML and noise."""
    if not text:
        return None
    cleaned = html.unescape(re.sub(r"<[^>]+>", "", text))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # Drop deleted/removed/bot noise and very short text.
    if cleaned.lower() in ("[deleted]", "[removed]", "") or len(cleaned) < 25:
        return None
    if len(cleaned) > 300:
        cleaned = f"{cleaned[:297]}..."
    return cleaned


def _extract_post_id(url: str) -> Optional[str]:
    """Extract the Reddit post ID from a URL like /r/movies/comments/abc123/..."""
    match = re.search(r"/comments/([a-z0-9]+)", url)
    return match.group(1) if match else None


# ---------------------------------------------------------------------------
# RSS: Search posts
# ---------------------------------------------------------------------------
def _search_posts_rss(
    title: str,
    subreddits: tuple,
    limit: int = 5,
) -> List[Dict]:
    """Search Reddit for posts about *title* via RSS search."""
    posts: List[Dict] = []
    for sub in subreddits:
        url = (
            f"https://www.reddit.com/r/{sub}/search.rss"
            f"?q={quote_plus(title)}&restrict_sr=1&sort=hot&t=week&limit={limit}"
        )
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries or []:
                entry_title = entry.get("title", "")
                link = entry.get("link", "")
                post_id = _extract_post_id(link)
                if not post_id:
                    continue
                posts.append({
                    "subreddit": sub,
                    "title": entry_title,
                    "link": link,
                    "post_id": post_id,
                })
        except Exception as exc:
            logger.debug("Reddit RSS search r/%s: %s", sub, exc)
        # Polite delay between subreddits.
        time.sleep(random.uniform(0.5, 1.2))

    return posts


# ---------------------------------------------------------------------------
# RSS: Hot posts (trending discovery)
# ---------------------------------------------------------------------------
def _fetch_hot_posts_rss(
    subreddits: tuple,
    limit: int = 10,
) -> List[Dict]:
    """Fetch hot/trending posts from subreddits via RSS."""
    posts: List[Dict] = []
    for sub in subreddits:
        url = f"https://www.reddit.com/r/{sub}/hot.rss?limit={limit}"
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries or []:
                entry_title = entry.get("title", "")
                link = entry.get("link", "")
                post_id = _extract_post_id(link)
                if not post_id:
                    continue
                posts.append({
                    "subreddit": sub,
                    "title": entry_title,
                    "link": link,
                    "post_id": post_id,
                })
        except Exception as exc:
            logger.debug("Reddit hot RSS r/%s: %s", sub, exc)
        time.sleep(random.uniform(0.3, 0.8))

    return posts


# ---------------------------------------------------------------------------
# RSS: Fetch comments for a specific post
# ---------------------------------------------------------------------------
def _fetch_comments_rss(
    post_id: str,
    max_comments: int = 15,
) -> List[str]:
    """Fetch comments for a Reddit post via RSS (/comments/{id}/.rss)."""
    url = f"https://www.reddit.com/comments/{post_id}/.rss"
    try:
        feed = feedparser.parse(url)
    except Exception as exc:
        logger.debug("Reddit comment RSS for %s: %s", post_id, exc)
        return []

    comments: List[str] = []
    for entry in feed.entries or []:
        # RSS comments have content in 'content' list or 'summary'.
        raw = ""
        if entry.get("content"):
            raw = entry["content"][0].get("value", "")
        elif entry.get("summary"):
            raw = entry["summary"]

        cleaned = _clean(raw)
        if cleaned:
            comments.append(cleaned)
        if len(comments) >= max_comments:
            break

    return comments


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_reddit_discussion(
    title: str,
    media_type: str = "movie",
    max_comments: int = 10,
    max_posts: int = 3,
) -> Dict:
    """
    Collect Reddit discussion comments about a movie/TV title.

    Strategy:
        1. RSS search for posts mentioning the title
        2. For the top posts, fetch comments via RSS

    Returns dict:
        comments: List[str]     — cleaned audience comments
        post_count: int         — relevant posts found
        sources: List[str]      — subreddits with discussion
    """
    subs = _TV_SUBS if media_type == "tv" else _MOVIE_SUBS

    # Search for posts about this title.
    posts = _search_posts_rss(title, subs, limit=5)

    # Filter to posts whose title mentions the movie/show.
    relevant = [p for p in posts if title.lower() in p["title"].lower()]
    if not relevant:
        relevant = posts  # Use whatever we got.
    relevant = relevant[:max_posts]

    comments: List[str] = []
    sources: List[str] = []
    per_post = max(3, max_comments // max(1, len(relevant)))

    for post in relevant:
        if post["subreddit"] not in sources:
            sources.append(post["subreddit"])

        post_comments = _fetch_comments_rss(post["post_id"], per_post)
        comments.extend(post_comments)

        if len(comments) >= max_comments:
            break
        # Small delay between comment fetches.
        time.sleep(random.uniform(0.3, 0.7))

    return {
        "comments": comments[:max_comments],
        "post_count": len(relevant),
        "sources": sources,
    }


def get_reddit_trending(media_type: str = "movie", limit: int = 10) -> List[Dict]:
    """
    Get currently hot/trending posts from movie/TV subreddits.

    Returns list of dicts with: subreddit, title, link, post_id.
    Useful for discovering what people are discussing RIGHT NOW.
    """
    subs = _TV_SUBS if media_type == "tv" else _MOVIE_SUBS
    return _fetch_hot_posts_rss(subs, limit=limit)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    print("=== Reddit Discussion Search ===")
    result = get_reddit_discussion("Scary Movie", "movie", max_comments=5)
    print(f"Posts: {result['post_count']}, Sources: {result['sources']}")
    for c in result["comments"][:5]:
        print(f"  > {c[:150]}")

    print("\n=== Reddit Trending ===")
    trending = get_reddit_trending("movie", limit=5)
    for t in trending[:5]:
        print(f"  [{t['subreddit']}] {t['title'][:100]}")
