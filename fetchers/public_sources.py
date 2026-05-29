import html
import re
from typing import List, Optional

import requests

STACKEXCHANGE_URL = "https://api.stackexchange.com/2.3/search/advanced"
HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "")


def _clean_comment(text: str) -> Optional[str]:
    if not text:
        return None
    cleaned = html.unescape(_strip_html(text)).replace("\n", " ").strip()
    if len(cleaned) < 15:
        return None
    return cleaned


def search_stackexchange_discussion(
    title: str,
    year: Optional[int] = None,
    limit: int = 10,
) -> List[str]:
    query = f"{title} {year}" if year else title

    try:
        response = requests.get(
            STACKEXCHANGE_URL,
            params={
                "order": "desc",
                "sort": "votes",
                "title": query,
                "site": "movies",
                "filter": "withbody",
                "pagesize": min(limit, 10),
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        comments: List[str] = []
        for item in data.get("items", []):
            body = item.get("body") or item.get("body_markdown") or ""
            cleaned = _clean_comment(body)
            if cleaned:
                comments.append(cleaned)
        return comments[:limit]
    except Exception as exc:
        print(f"StackExchange request failed: {exc}")
        return []


def search_hn_discussion(
    title: str,
    year: Optional[int] = None,
    limit: int = 10,
) -> List[str]:
    query = f"{title} {year}" if year else title

    try:
        response = requests.get(
            HN_SEARCH_URL,
            params={
                "query": query,
                "tags": "comment",
                "hitsPerPage": min(limit, 20),
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        comments: List[str] = []
        for item in data.get("hits", []):
            cleaned = _clean_comment(item.get("comment_text", ""))
            if cleaned:
                comments.append(cleaned)
        return comments[:limit]
    except Exception as exc:
        print(f"Hacker News request failed: {exc}")
        return []


def get_public_comments(
    title: str,
    year: Optional[int] = None,
    max_per_source: int = 5,
) -> List[str]:
    comments = []
    comments.extend(search_stackexchange_discussion(title, year, max_per_source))
    comments.extend(search_hn_discussion(title, year, max_per_source))
    return comments

