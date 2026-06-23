"""YouTube trailer comments fetcher via Data API v3."""

import html
import logging
import os
import re
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
YT_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YT_COMMENTS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"


def _clean_comment(text: str) -> Optional[str]:
    """Clean YouTube comment text."""
    if not text:
        return None
    cleaned = html.unescape(re.sub(r"<[^>]+>", "", text)).replace("\n", " ").strip()
    if len(cleaned) < 15:
        return None
    if len(cleaned) > 250:
        cleaned = f"{cleaned[:247]}..."
    return cleaned


def _find_trailer_video_id(title: str, year: Optional[int] = None) -> Optional[str]:
    """Search YouTube for a movie trailer and return video ID."""
    if not YOUTUBE_API_KEY:
        return None

    query = f"{title} official trailer"
    if year:
        query += f" {year}"

    try:
        response = requests.get(
            YT_SEARCH_URL,
            params={
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": 1,
                "key": YOUTUBE_API_KEY,
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        items = data.get("items", [])
        if items:
            return items[0]["id"]["videoId"]
        return None
    except Exception as exc:
        logger.error("YouTube search failed for '%s': %s", title, exc)
        return None


def _fetch_video_comments(video_id: str, max_comments: int = 20) -> List[str]:
    """Fetch top comments from a YouTube video."""
    if not YOUTUBE_API_KEY:
        return []

    try:
        response = requests.get(
            YT_COMMENTS_URL,
            params={
                "part": "snippet",
                "videoId": video_id,
                "order": "relevance",
                "maxResults": min(max_comments, 50),
                "key": YOUTUBE_API_KEY,
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        comments: List[str] = []
        for item in data.get("items", []):
            snippet = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
            text = snippet.get("textDisplay", "")
            cleaned = _clean_comment(text)
            if cleaned:
                comments.append(cleaned)

        return comments

    except Exception as exc:
        logger.error("YouTube comments failed for video %s: %s", video_id, exc)
        return []


def get_trailer_comments(
    title: str,
    year: Optional[int] = None,
    max_comments: int = 10,
) -> Dict:
    """
    Find a movie trailer on YouTube and return top comments.

    Returns dict with keys:
        video_id: str|None      — YouTube video ID
        comments: List[str]     — cleaned top comments
        comment_count: int      — number of comments returned
    """
    if not YOUTUBE_API_KEY:
        logger.info("YOUTUBE_API_KEY is missing. YouTube comments unavailable")
        return {"video_id": None, "comments": [], "comment_count": 0}

    video_id = _find_trailer_video_id(title, year)
    if not video_id:
        return {"video_id": None, "comments": [], "comment_count": 0}

    comments = _fetch_video_comments(video_id, max_comments)

    return {
        "video_id": video_id,
        "comments": comments[:max_comments],
        "comment_count": len(comments),
    }


if __name__ == "__main__":
    result = get_trailer_comments("Sinners", 2025)
    print(f"Video: {result['video_id']}, Comments: {result['comment_count']}")
    for c in result["comments"][:3]:
        print(f"  > {c[:100]}")
