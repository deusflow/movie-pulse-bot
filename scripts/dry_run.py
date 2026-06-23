"""Dry run script — verifies the entire pipeline by simulating TMDB trending and printing formatted HTML posts."""

import logging
import os
import sys

# Ensure project root is on path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch
from main import enrich_item
from formatter import build_daily_post
from locales import get_strings

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Mock TMDB data for testing (2 movies + 2 TV shows).
MOCK_TRENDING = [
    {
        "id": 693134,
        "title": "Dune: Part Two",
        "media_type": "movie",
        "genre_ids": [878, 12],  # Sci-Fi, Adventure
        "overview": "Paul Atreides unites with Chani and the Fremen while seeking revenge against the conspirators who destroyed his family.",
        "poster_path": "/1pdfPm1HG3gKsFS3u0qCcZ965S8.jpg",
        "vote_average": 8.3,
        "popularity": 120.5,
        "release_date": "2024-03-01",
    },
    {
        "id": 94997,
        "name": "House of the Dragon",
        "media_type": "tv",
        "genre_ids": [18, 10765],  # Drama, Sci-Fi & Fantasy
        "overview": "The Targaryen dynasty is at the absolute apex of its power, with more than 15 dragons under their yoke.",
        "poster_path": "/z2yahl2uefxDCl0nogcRBstwruJ.jpg",
        "vote_average": 8.4,
        "popularity": 110.3,
        "first_air_date": "2022-08-21",
    },
    {
        "id": 533535,
        "title": "Deadpool & Wolverine",
        "media_type": "movie",
        "genre_ids": [28, 35, 878],  # Action, Comedy, Sci-Fi
        "overview": "A listless Wade Wilson toils in civilian life with his days as the morally flexible mercenary, Deadpool, behind him.",
        "poster_path": "/8cdRyL5jVMXM10tZ880q6VM9egV.jpg",
        "vote_average": 7.7,
        "popularity": 95.2,
        "release_date": "2024-07-26",
    },
    {
        "id": 239770,
        "name": "The Bear",
        "media_type": "tv",
        "genre_ids": [18, 35],  # Drama, Comedy
        "overview": "A young chef from the fine dining world returns to Chicago to run his family's Italian beef sandwich shop.",
        "poster_path": "/sHFlqEjAhGUMhQLbMpas4YMBJvw.jpg",
        "vote_average": 8.6,
        "popularity": 88.1,
        "first_air_date": "2022-06-23",
    },
]

MOCK_COMMENTS = {
    "Dune: Part Two": [
        "Absolutely a masterpiece! Visually stunning with an incredible sound design. Denis Villeneuve did it again.",
        "The story drags a bit in the second act, and some character motivations feel rushed compared to the book.",
        "Timothee Chalamet and Zendaya have great chemistry. The sandworm riding scene was spectacular!",
        "It's too long. Three hours of sand and political whispering is a bit tedious.",
    ],
    "House of the Dragon": [
        "The political intrigue is fantastic, way better than the last seasons of GoT.",
        "Too many characters, hard to keep track of who's who.",
        "The dragon scenes are incredible, best CGI on TV right now.",
        "Slow pacing at times, but the payoff is worth it.",
    ],
    "Deadpool & Wolverine": [
        "So hilariously funny! Hugh Jackman was amazing. The cameos are legendary.",
        "A typical Marvel movie with a CGI-heavy third act and a weak villain, but the jokes make up for it.",
        "Loved the meta-humor and references, but the plot is practically non-existent.",
        "Best Deadpool movie yet. Ryan Reynolds is perfect.",
    ],
    "The Bear": [
        "Best show on TV right now. The kitchen scenes give me anxiety in the best way.",
        "Season 3 lost the magic. Too much filler, not enough plot movement.",
        "Jeremy Allen White deserves every award. The acting is phenomenal.",
        "Great acting but the constant yelling gets exhausting.",
    ],
}

MOCK_SCORES = {
    "Dune: Part Two": {
        "tmdb_popularity": 120.5,
        "tmdb_vote": 8.3,
        "rt_score": 92,
        "metascore": 79,
        "imdb_rating": 8.6,
        "imdb_votes": "450K",
        "press_mention_count": 5,
        "press_sources": ["Roger Ebert", "Variety"],
        "news_mentions": 12,
        "news_snippets": [],
        "buzz_score": 87,
        "omdb_poster_url": None,
    },
    "House of the Dragon": {
        "tmdb_popularity": 110.3,
        "tmdb_vote": 8.4,
        "rt_score": 88,
        "metascore": 75,
        "imdb_rating": 8.4,
        "imdb_votes": "320K",
        "press_mention_count": 4,
        "press_sources": ["Variety", "Hollywood Reporter"],
        "news_mentions": 10,
        "news_snippets": [],
        "buzz_score": 84,
        "omdb_poster_url": None,
    },
    "Deadpool & Wolverine": {
        "tmdb_popularity": 95.2,
        "tmdb_vote": 7.7,
        "rt_score": 78,
        "metascore": 56,
        "imdb_rating": 7.8,
        "imdb_votes": "210K",
        "press_mention_count": 3,
        "press_sources": ["Hollywood Reporter"],
        "news_mentions": 8,
        "news_snippets": [],
        "buzz_score": 72,
        "omdb_poster_url": None,
    },
    "The Bear": {
        "tmdb_popularity": 88.1,
        "tmdb_vote": 8.6,
        "rt_score": 96,
        "metascore": 84,
        "imdb_rating": 8.7,
        "imdb_votes": "180K",
        "press_mention_count": 6,
        "press_sources": ["Roger Ebert", "IndieWire"],
        "news_mentions": 9,
        "news_snippets": [],
        "buzz_score": 90,
        "omdb_poster_url": None,
    },
}


def mock_get_trending_all(limit=20):
    return MOCK_TRENDING[:limit]


def mock_aggregate_comments(title, tmdb_id=None, year=None, media_type="movie", max_per_source=5):
    return MOCK_COMMENTS.get(title, ["A great movie that everyone should see!", "Some parts were slow."])


def mock_aggregate_scores(title, tmdb_item, year=None):
    return MOCK_SCORES.get(title, {
        "tmdb_popularity": 50.0,
        "tmdb_vote": 6.0,
        "rt_score": 60,
        "metascore": 50,
        "imdb_rating": 6.5,
        "imdb_votes": None,
        "press_mention_count": 0,
        "press_sources": [],
        "news_mentions": 0,
        "news_snippets": [],
        "buzz_score": 58,
        "omdb_poster_url": None,
    })


def mock_is_recently_posted(title, tmdb_id, days=7):
    return False


@patch("main.get_trending_all", mock_get_trending_all)
@patch("main.aggregate_comments", mock_aggregate_comments)
@patch("main.aggregate_scores", mock_aggregate_scores)
@patch("main.is_recently_posted", mock_is_recently_posted)
def run_dry_run():
    logger.info("🎬 Starting Dry Run (Simulated Pipeline)...\n")

    # 1. Select slots from mock data.
    from main import select_slots
    s1, s2, s3, s4 = select_slots(MOCK_TRENDING)

    logger.info("🎯 Selected Mock Slots:")
    logger.info("  1. %s (Movie #1)", s1.get('title') or s1.get('name'))
    logger.info("  2. %s (Series #1)", s2.get('title') or s2.get('name'))
    logger.info("  3. %s (Movie #2)", s3.get('title') or s3.get('name'))
    logger.info("  4. %s (Series #2)", s4.get('title') or s4.get('name'))

    # Determine languages to generate.
    languages = ["en"]
    if os.getenv("TELEGRAM_CHANNEL_ID_UK") or os.getenv("DRY_RUN_ALL_LANGS"):
        languages.append("uk")

    for lang in languages:
        logger.info("\n%s", "=" * 42)
        logger.info("🌍 LANGUAGE: %s", lang.upper())
        logger.info("%s", "=" * 42)

        # Enrich mock items.
        logger.info("\n🔍 Enriching slot 1 (Movie #1)...")
        movie1 = enrich_item(s1, lang)

        logger.info("\n🔍 Enriching slot 2 (Series #1)...")
        series1 = enrich_item(s2, lang)

        logger.info("\n🔍 Enriching slot 3 (Movie #2)...")
        movie2 = enrich_item(s3, lang)

        logger.info("\n🔍 Enriching slot 4 (Series #2)...")
        series2 = enrich_item(s4, lang)

        # Build formatted post.
        logger.info("\n📝 Building post...")
        post = build_daily_post(movie1, series1, movie2, series2, lang)

        # Print post to console.
        logger.info("\n--- POST (Poster URL: %s) ---", post.get('poster_url'))
        logger.info("\n%s", post.get("text"))
        logger.info("-" * 42)


if __name__ == "__main__":
    # Force generating Ukrainian language as well for dry run.
    os.environ["DRY_RUN_ALL_LANGS"] = "true"
    run_dry_run()
