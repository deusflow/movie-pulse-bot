import os
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

# Load environment variables once at import time.
load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE_URL = "https://api.themoviedb.org/3"
POSTER_BASE_URL = "https://image.tmdb.org/t/p/w500"

GENRE_MAP: Dict[int, str] = {
    28: "Action",
    35: "Comedy",
    18: "Drama",
    27: "Horror",
    878: "Sci-Fi",
    10749: "Romance",
    53: "Thriller",
    16: "Animation",
    10751: "Family",
    80: "Crime",
    9648: "Mystery",
    12: "Adventure",
}


def _build_item(result: Dict) -> Dict:
    return {
        "id": result.get("id"),
        "title": result.get("title") or result.get("name"),
        "media_type": result.get("media_type"),
        "genre_ids": result.get("genre_ids", []),
        "overview": result.get("overview"),
        "poster_path": result.get("poster_path"),
        "vote_average": result.get("vote_average"),
        "release_date": result.get("release_date") or result.get("first_air_date"),
    }


def _fetch_trending() -> List[Dict]:
    if not TMDB_API_KEY:
        print("TMDB_API_KEY is missing. Set it in .env")
        return []

    try:
        response = requests.get(
            f"{TMDB_BASE_URL}/trending/all/day",
            params={"api_key": TMDB_API_KEY},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])
    except Exception as exc:
        print(f"TMDB trending request failed: {exc}")
        return []


def _fetch_discover_comedy() -> List[Dict]:
    if not TMDB_API_KEY:
        print("TMDB_API_KEY is missing. Set it in .env")
        return []

    try:
        response = requests.get(
            f"{TMDB_BASE_URL}/discover/movie",
            params={
                "api_key": TMDB_API_KEY,
                "with_genres": 35,
                "sort_by": "popularity.desc",
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])
    except Exception as exc:
        print(f"TMDB discover request failed: {exc}")
        return []


def get_trending_all() -> List[Dict]:
    """Return 10 trending items across all media types."""
    results = _fetch_trending()
    items = [_build_item(result) for result in results]
    return items[:10]


def get_comedy_trending() -> List[Dict]:
    """Return up to 3 comedy items, falling back to discover if needed."""
    results = _fetch_trending()
    comedy = [
        _build_item(result)
        for result in results
        if 35 in (result.get("genre_ids") or [])
    ]

    if len(comedy) < 3:
        discover_results = _fetch_discover_comedy()
        seen_ids = {item.get("id") for item in comedy}
        for result in discover_results:
            item = _build_item(result)
            if item.get("id") in seen_ids:
                continue
            comedy.append(item)
            seen_ids.add(item.get("id"))
            if len(comedy) >= 3:
                break

    return comedy[:3]


def get_poster_url(poster_path: Optional[str]) -> Optional[str]:
    if not poster_path:
        return None
    return f"{POSTER_BASE_URL}{poster_path}"


def get_genre_names(genre_ids: List[int]) -> str:
    names = [
        GENRE_MAP[genre_id] for genre_id in genre_ids if genre_id in GENRE_MAP
    ]
    return ", ".join(names)


if __name__ == "__main__":
    items = get_trending_all()
    print(f"Found {len(items)} trending")
    for i in items[:3]:
        t = i.get("title") or i.get("name")
        print(f"- {t} | {get_genre_names(i.get('genre_ids', []))}")
    print("\nComedy:")
    for c in get_comedy_trending():
        print(f"- {c.get('title') or c.get('name')}")
