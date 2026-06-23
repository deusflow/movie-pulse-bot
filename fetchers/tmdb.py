"""TMDB API fetcher — trending movies, genres, reviews, posters, streaming providers."""

import logging
import os
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE_URL = "https://api.themoviedb.org/3"
POSTER_BASE_URL = "https://image.tmdb.org/t/p/w500"

# Combined movie + TV genre IDs from TMDB.
GENRE_MAP: Dict[int, str] = {
    # --- Movie genres ---
    28: "Action",
    12: "Adventure",
    16: "Animation",
    35: "Comedy",
    80: "Crime",
    99: "Documentary",
    18: "Drama",
    10751: "Family",
    14: "Fantasy",
    36: "History",
    27: "Horror",
    10402: "Music",
    9648: "Mystery",
    10749: "Romance",
    878: "Sci-Fi",
    10770: "TV Movie",
    53: "Thriller",
    10752: "War",
    37: "Western",
    # --- TV genres ---
    10759: "Action & Adventure",
    10762: "Kids",
    10763: "News",
    10764: "Reality",
    10765: "Sci-Fi & Fantasy",
    10766: "Soap",
    10767: "Talk",
    10768: "War & Politics",
}

# TMDB watch provider IDs for major streaming platforms.
STREAMING_PROVIDERS: Dict[int, str] = {
    8: "Netflix",
    9: "Amazon Prime",
    337: "Disney+",
    350: "Apple TV+",
    531: "Paramount+",
    384: "HBO Max",
    15: "Hulu",
}


def _build_item(result: Dict) -> Dict:
    """Normalize a TMDB API result into a standard item dict."""
    return {
        "id": result.get("id"),
        "title": result.get("title") or result.get("name"),
        "original_title": result.get("original_title") or result.get("original_name", ""),
        "media_type": result.get("media_type", "movie"),
        "genre_ids": result.get("genre_ids", []),
        "overview": result.get("overview", ""),
        "poster_path": result.get("poster_path"),
        "vote_average": result.get("vote_average"),
        "popularity": result.get("popularity"),
        "release_date": result.get("release_date") or result.get("first_air_date"),
    }


def _fetch_trending() -> List[Dict]:
    """Fetch trending items from TMDB /trending/all/day."""
    if not TMDB_API_KEY:
        logger.warning("TMDB_API_KEY is missing")
        return []

    try:
        response = requests.get(
            f"{TMDB_BASE_URL}/trending/all/day",
            params={"api_key": TMDB_API_KEY},
            timeout=10,
        )
        response.raise_for_status()
        return response.json().get("results", [])
    except Exception as exc:
        logger.error("TMDB trending request failed: %s", exc)
        return []


def get_trending_all(limit: int = 20) -> List[Dict]:
    """Return trending items across all media types."""
    results = _fetch_trending()
    items = [_build_item(r) for r in results]
    return items[:limit]


def search_by_title(title: str, media_type: str = "movie") -> Optional[Dict]:
    """
    Search TMDB for a movie or TV show by title.

    Returns the first matching result as a normalized item dict,
    or None if no match is found.
    """
    if not TMDB_API_KEY or not title:
        return None

    endpoint = "tv" if media_type == "tv" else "movie"

    try:
        response = requests.get(
            f"{TMDB_BASE_URL}/search/{endpoint}",
            params={"api_key": TMDB_API_KEY, "query": title, "language": "en-US"},
            timeout=10,
        )
        response.raise_for_status()
        results = response.json().get("results", [])
        if not results:
            logger.debug("TMDB search found nothing for '%s' (%s)", title, media_type)
            return None

        # Take the first (most relevant) result.
        best = results[0]
        best["media_type"] = media_type
        return _build_item(best)

    except Exception as exc:
        logger.warning("TMDB search failed for '%s': %s", title, exc)
        return None


def get_poster_url(poster_path: Optional[str]) -> Optional[str]:
    """Build a full poster URL from a TMDB poster_path."""
    if not poster_path:
        return None
    if str(poster_path).startswith("http"):
        return str(poster_path)
    return f"{POSTER_BASE_URL}{poster_path}"


def get_genre_names(genre_ids: List[int]) -> str:
    """Convert genre ID list to a comma-separated genre name string."""
    names = [GENRE_MAP[gid] for gid in genre_ids if gid in GENRE_MAP]
    return ", ".join(names) if names else "Unknown"


def get_movie_reviews(
    tmdb_id: Optional[int],
    media_type: str = "movie",
    limit: int = 8,
) -> List[str]:
    """Fetch user reviews for a movie or TV show from TMDB."""
    if not TMDB_API_KEY or not tmdb_id:
        return []

    endpoint = "tv" if media_type == "tv" else "movie"

    try:
        response = requests.get(
            f"{TMDB_BASE_URL}/{endpoint}/{tmdb_id}/reviews",
            params={"api_key": TMDB_API_KEY},
            timeout=10,
        )
        response.raise_for_status()
        reviews = response.json().get("results", [])
        contents = [r.get("content", "").strip() for r in reviews]
        return [c for c in contents if c][:limit]
    except Exception as exc:
        logger.error("TMDB reviews failed for %s/%s: %s", endpoint, tmdb_id, exc)
        return []


def get_watch_providers(
    tmdb_id: Optional[int],
    media_type: str = "movie",
    region: str = "US",
) -> List[str]:
    """
    Get streaming platform names where this title is available.

    Uses TMDB /movie/{id}/watch/providers or /tv/{id}/watch/providers.
    Returns list of platform names (e.g. ["Netflix", "Apple TV+"]).
    """
    if not TMDB_API_KEY or not tmdb_id:
        return []

    endpoint = "tv" if media_type == "tv" else "movie"

    try:
        response = requests.get(
            f"{TMDB_BASE_URL}/{endpoint}/{tmdb_id}/watch/providers",
            params={"api_key": TMDB_API_KEY},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json().get("results", {})

        # Get providers for the specified region.
        region_data = data.get(region, {})
        # "flatrate" = subscription streaming (Netflix, Disney+, etc.)
        flatrate = region_data.get("flatrate", [])

        providers = []
        for p in flatrate:
            pid = p.get("provider_id")
            name = STREAMING_PROVIDERS.get(pid) or p.get("provider_name", "")
            if name and name not in providers:
                providers.append(name)

        return providers[:5]
    except Exception as exc:
        logger.debug("TMDB watch providers failed for %s/%s: %s", endpoint, tmdb_id, exc)
        return []


def extract_year(item: Dict) -> Optional[int]:
    """Extract release year from a TMDB item."""
    date_str = item.get("release_date") or item.get("first_air_date")
    if not date_str:
        return None
    try:
        return int(str(date_str)[:4])
    except (ValueError, TypeError):
        return None


def get_item_details(tmdb_id: int, media_type: str) -> Dict[str, int]:
    """
    Fetch specific details like number of episodes or collection parts.
    Returns: {"episodes_count": int, "parts_count": int}
    """
    result = {"episodes_count": 0, "parts_count": 0}
    if not TMDB_API_KEY or not tmdb_id:
        return result

    try:
        if media_type == "tv":
            resp = requests.get(
                f"{TMDB_BASE_URL}/tv/{tmdb_id}",
                params={"api_key": TMDB_API_KEY},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                result["episodes_count"] = data.get("number_of_episodes", 0)
                
        elif media_type == "movie":
            resp = requests.get(
                f"{TMDB_BASE_URL}/movie/{tmdb_id}",
                params={"api_key": TMDB_API_KEY},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                collection = data.get("belongs_to_collection")
                if collection and collection.get("id"):
                    col_resp = requests.get(
                        f"{TMDB_BASE_URL}/collection/{collection['id']}",
                        params={"api_key": TMDB_API_KEY},
                        timeout=10,
                    )
                    if col_resp.status_code == 200:
                        col_data = col_resp.json()
                        result["parts_count"] = len(col_data.get("parts", []))
    except Exception as exc:
        logger.debug("TMDB details failed for %s/%s: %s", media_type, tmdb_id, exc)

    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    items = get_trending_all()
    print(f"Found {len(items)} trending")
    for i in items[:3]:
        print(f"- {i['title']} | {get_genre_names(i['genre_ids'])}")
        providers = get_watch_providers(i["id"], i["media_type"])
        if providers:
            print(f"  Streaming: {', '.join(providers)}")
