"""Rotten Tomatoes audience-review fetcher.

RT loads audience reviews dynamically via JavaScript (web components).
Static HTML scraping can only extract the reviewsData JSON metadata
embedded in the page (emsId, scores, title info), but NOT the actual
review text.

This module tries to extract whatever is available from the static page.
If no reviews can be scraped, it returns an empty result gracefully —
the bot continues with Reddit + other sources.
"""

import html
import json
import logging
import re
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

RT_BASE = "https://www.rottentomatoes.com"

# Realistic headers to avoid bot detection.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


def _clean(text: str) -> Optional[str]:
    """Clean review text, stripping HTML tags and normalizing whitespace."""
    if not text:
        return None
    cleaned = html.unescape(re.sub(r"<[^>]+>", "", text))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) < 20:
        return None
    if len(cleaned) > 300:
        cleaned = f"{cleaned[:297]}..."
    return cleaned


def _slugify(title: str) -> str:
    """Build a best-effort RT URL slug from a title."""
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    return slug


def _extract_metadata(page_html: str) -> Dict:
    """Extract review metadata from the embedded JSON in the RT page."""
    try:
        match = re.search(
            r'<script\s+type="application/json"\s+data-json="reviewsData">\s*({.*?})\s*</script>',
            page_html,
            re.DOTALL,
        )
        if match:
            data = json.loads(match.group(1))
            media = data.get("media", {})
            return {
                "ems_id": media.get("emsId"),
                "title": media.get("title"),
                "tomatometer": media.get("tomatometerScore", {}).get("value"),
                "rating": media.get("rating"),
            }
    except (json.JSONDecodeError, AttributeError) as exc:
        logger.debug("RT metadata extraction failed: %s", exc)
    return {}


def _scrape_critic_quotes(page_html: str, limit: int = 10) -> List[str]:
    """Try to extract critic review quotes from the static HTML."""
    quotes: List[str] = []

    # Pattern 1: review-quote or review_quote attributes.
    patterns = [
        r'data-qa="review-quote"[^>]*>(.*?)</p>',
        r'class="[^"]*review-quote[^"]*"[^>]*>(.*?)</(?:p|div|span)>',
        r'class="[^"]*review_quote[^"]*"[^>]*>(.*?)</(?:p|div|span)>',
        r'class="[^"]*the_review[^"]*"[^>]*>(.*?)</(?:p|div|span)>',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, page_html, re.DOTALL | re.IGNORECASE)
        for raw in matches:
            cleaned = _clean(raw)
            if cleaned and cleaned not in quotes:
                quotes.append(cleaned)
            if len(quotes) >= limit:
                return quotes

    return quotes


def get_audience_reviews(
    title: str,
    media_type: str = "movie",
    max_reviews: int = 10,
) -> Dict:
    """
    Attempt to collect Rotten Tomatoes reviews for a title.

    RT audience reviews are loaded via JavaScript and cannot be scraped
    from static HTML. This function tries to extract whatever is available
    (critic quotes, metadata) and returns gracefully if nothing is found.

    Returns dict:
        comments: List[str]     — review snippets (may be empty)
        review_count: int       — number of reviews found
        metadata: Dict          — RT metadata (emsId, tomatometer, etc.)
    """
    slug = _slugify(title)
    kind = "tv" if media_type == "tv" else "m"
    reviews: List[str] = []
    metadata: Dict = {}

    # Try the audience reviews page first.
    try:
        url = f"{RT_BASE}/{kind}/{slug}/reviews?type=user"
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        if resp.status_code == 200:
            metadata = _extract_metadata(resp.text)
            # Audience reviews are JS-rendered, but try critic quotes.
            reviews = _scrape_critic_quotes(resp.text, limit=max_reviews)
    except Exception as exc:
        logger.debug("RT audience page failed for '%s': %s", title, exc)

    # If no audience reviews, try the critics page for quotes.
    if not reviews:
        try:
            url = f"{RT_BASE}/{kind}/{slug}/reviews"
            resp = requests.get(url, headers=_HEADERS, timeout=15)
            if resp.status_code == 200:
                reviews = _scrape_critic_quotes(resp.text, limit=max_reviews)
                if not metadata:
                    metadata = _extract_metadata(resp.text)
        except Exception as exc:
            logger.debug("RT critics page failed for '%s': %s", title, exc)

    reviews = reviews[:max_reviews]
    return {
        "comments": reviews,
        "review_count": len(reviews),
        "metadata": metadata,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    res = get_audience_reviews("Sinners", "movie")
    print(f"Reviews: {res['review_count']}, Metadata: {res['metadata']}")
    for c in res["comments"][:5]:
        print(f"  > {c[:120]}")
