"""OMDb API fetcher — Rotten Tomatoes, Metascore, IMDb ratings."""

import logging

import os
from typing import Dict, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

OMDB_API_KEY = os.getenv("OMDB_API_KEY", "")
OMDB_API_URL = "http://www.omdbapi.com/"


def _fetch_omdb(title: str, year: Optional[int] = None) -> Optional[Dict]:
    """Fetch movie data from OMDb by title (and optional year)."""
    if not OMDB_API_KEY:
        logger.warning("OMDB_API_KEY is missing. OMDb data unavailable")
        return None

    params = {"t": title, "apikey": OMDB_API_KEY, "type": "movie"}
    if year:
        params["y"] = str(year)

    try:
        response = requests.get(OMDB_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("Response") == "False":
            return None
        return data
    except Exception as exc:
        logger.error("OMDb request failed for '%s': %s", title, exc)
        return None


def _parse_rt_score(ratings: list) -> Optional[int]:
    """Extract Rotten Tomatoes percentage from OMDb Ratings array."""
    for rating in ratings:
        if rating.get("Source") == "Rotten Tomatoes":
            value = rating.get("Value", "")
            try:
                return int(value.replace("%", ""))
            except (ValueError, TypeError):
                return None
    return None


def _parse_int(value: str) -> Optional[int]:
    """Safely parse a numeric string, returning None on failure."""
    if not value or value == "N/A":
        return None
    try:
        return int(value.replace("/100", ""))
    except (ValueError, TypeError):
        return None


def _parse_float(value: str) -> Optional[float]:
    """Safely parse a float string like '7.8/10'."""
    if not value or value == "N/A":
        return None
    try:
        return float(value.split("/")[0])
    except (ValueError, TypeError):
        return None


def get_movie_scores(title: str, year: Optional[int] = None) -> Dict:
    """
    Return aggregated scores for a movie from OMDb.

    Returns dict with keys:
        rt_score: int|None      — Rotten Tomatoes %
        metascore: int|None     — Metacritic score (0-100)
        imdb_rating: float|None — IMDb rating (0-10)
        imdb_votes: str|None    — IMDb vote count
        poster_url: str|None    — Movie poster URL
    """
    data = _fetch_omdb(title, year)
    if not data:
        return {
            "rt_score": None,
            "metascore": None,
            "imdb_rating": None,
            "imdb_votes": None,
            "poster_url": None,
        }

    poster = data.get("Poster")
    if poster == "N/A":
        poster = None

    return {
        "rt_score": _parse_rt_score(data.get("Ratings", [])),
        "metascore": _parse_int(data.get("Metascore", "")),
        "imdb_rating": _parse_float(data.get("imdbRating", "")),
        "imdb_votes": data.get("imdbVotes") if data.get("imdbVotes") != "N/A" else None,
        "poster_url": poster,
    }


if __name__ == "__main__":
    scores = get_movie_scores("Sinners", 2025)
    print(scores)
