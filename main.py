"""Movie Pulse Bot — daily movie news aggregator and Telegram poster.

Architecture: Discussions-First
    1. SCAN   — Collect discussions from 5+ sources (Reddit, YouTube, News, Press, TMDB)
    2. AI     — ONE AI call to pick Top 2 movies + Top 2 series from all discussions
    3. ENRICH — Fetch details only for the 4 selected items (TMDB, OMDb, streaming)
    4. POST   — Format and send to Telegram channels
"""

import logging
import os
import time
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv

# Load .env at the very top.
load_dotenv()

# Configure logging for the entire application.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

from ai.gemini import pick_top_from_discussions
from bot.sender import send_daily_post_to_all
from fetchers.discovery import discover_discussions
from fetchers.omdb import get_movie_scores
from fetchers.tmdb import (
    extract_year,
    get_genre_names,
    get_poster_url,
    get_trending_all,
    get_item_details,
    get_watch_providers,
    search_by_title,
)
from formatter import build_daily_post
from db.database import init_db, is_recently_posted, save_publication, save_daily_top


def enrich_selected_item(pick: Dict, discussions: List[Dict]) -> Dict:
    """
    Enrich an AI-selected pick with TMDB details, scores, and streaming info.
    NO AI call here — just data fetching.

    Args:
        pick: AI pick dict with: title, media_type, score, positive_comment,
              negative_comment, one_line_summary
        discussions: Original discussion list (to find TMDB data if available)

    Returns:
        Enriched item dict ready for formatting and DB saving.
    """
    title = pick.get("title", "Unknown")
    media_type = pick.get("media_type", "movie")

    logger.info("  🔍 Enriching '%s' (%s)...", title, media_type)

    # Step 1: Find TMDB data.
    # First, check if this title already exists in our TMDB discovery data.
    tmdb_item = None
    for disc in discussions:
        if disc.get("source") == "tmdb_trending" and disc.get("tmdb_data"):
            disc_title = disc.get("title_raw", "").lower()
            if disc_title == title.lower() or title.lower() in disc_title:
                tmdb_item = disc["tmdb_data"]
                logger.info("    ✅ Found in TMDB trending cache")
                break

    # If not in cache, search TMDB by title.
    if not tmdb_item:
        logger.info("    🔎 Searching TMDB for '%s'...", title)
        tmdb_item = search_by_title(title, media_type)

    if not tmdb_item:
        logger.warning("    ⚠️ '%s' not found on TMDB", title)
        tmdb_item = {
            "id": None,
            "title": title,
            "media_type": media_type,
            "genre_ids": [],
            "overview": "",
            "poster_path": None,
            "vote_average": 0,
            "popularity": 0,
            "release_date": None,
        }

    tmdb_id = tmdb_item.get("id")
    year = extract_year(tmdb_item)
    genre_names = get_genre_names(tmdb_item.get("genre_ids", []))

    # Step 2: Get OMDb scores.
    logger.info("    📊 Collecting scores for '%s'...", title)
    omdb = get_movie_scores(title, year)

    # Step 3: Get TMDB details (episodes, parts).
    details = {"episodes_count": 0, "parts_count": 0}
    if tmdb_id:
        details = get_item_details(tmdb_id, media_type)

    # Step 4: Get streaming platforms.
    streaming = []
    if tmdb_id:
        streaming = get_watch_providers(tmdb_id, media_type)

    # Step 5: Determine poster URL.
    poster_url = get_poster_url(tmdb_item.get("poster_path"))
    if not poster_url:
        poster_url = omdb.get("poster_url")

    # Build the enriched item.
    return {
        # TMDB base data
        **tmdb_item,
        # AI analysis results
        "score": pick.get("score", 50),
        "positive_comments": [pick["positive_comment"]] if pick.get("positive_comment") else [],
        "negative_comments": [pick["negative_comment"]] if pick.get("negative_comment") else [],
        "one_line_summary": pick.get("one_line_summary", ""),
        "relevance": "high",
        # Scores from OMDb
        **omdb,
        # TMDB details
        **details,
        # Computed/merged fields
        "title": title,
        "media_type": media_type,
        "genres": genre_names,
        "poster_url": poster_url,
        "streaming_platforms": streaming,
        "buzz_score": pick.get("score", 50),
        "discussion_count": 0,  # Will be set later if we add comment collection
    }


def run() -> None:
    """Main bot pipeline — discussions-first architecture."""
    logger.info("🎬 Starting Movie Pulse Bot...")
    init_db()

    # ═══════════════════════════════════════════════════════
    # STEP 1: Scan discussions from ALL sources
    # ═══════════════════════════════════════════════════════
    logger.info("📡 Step 1: Scanning discussions from all sources...")
    discussions = discover_discussions()

    if not discussions:
        logger.error("❌ No discussions found from any source")
        return

    # ═══════════════════════════════════════════════════════
    # STEP 2: AI picks Top 2 movies + Top 2 series (1 call)
    # ═══════════════════════════════════════════════════════
    languages = ["en"]
    if os.getenv("TELEGRAM_CHANNEL_ID_UK"):
        languages.append("uk")

    posts_by_lang = {}
    enriched_items = []

    for lang in languages:
        logger.info("🌍 Processing language: %s", lang)

        logger.info("🤖 Step 2: AI analyzing %d discussions...", len(discussions))
        top_picks = pick_top_from_discussions(discussions, lang=lang)

        logger.info("🎯 AI selected:")
        for i, pick in enumerate(top_picks, 1):
            slot = ["Movie #1", "Series #1", "Movie #2", "Series #2"][i - 1]
            logger.info("  %d. %s (%s)", i, pick["title"], slot)

        # Check for duplicates with recently posted
        for pick in top_picks:
            if is_recently_posted(None, pick["media_type"], title=pick["title"]):
                logger.info("⚠️ '%s' was recently posted — keeping anyway (AI chose it)", pick["title"])

        # ═══════════════════════════════════════════════════
        # STEP 3: Enrich only the 4 selected items (NO AI)
        # ═══════════════════════════════════════════════════
        logger.info("📦 Step 3: Enriching selected items...")

        movie1 = enrich_selected_item(top_picks[0], discussions)
        series1 = enrich_selected_item(top_picks[1], discussions)
        movie2 = enrich_selected_item(top_picks[2], discussions)
        series2 = enrich_selected_item(top_picks[3], discussions)

        # ═══════════════════════════════════════════════════
        # STEP 4: Build formatted post
        # ═══════════════════════════════════════════════════
        logger.info("📝 Building post (%s)...", lang)
        post = build_daily_post(movie1, series1, movie2, series2, lang)
        posts_by_lang[lang] = post

        # Save enriched items from the first language processed.
        if not enriched_items:
            enriched_items = [movie1, series1, movie2, series2]

    # ═══════════════════════════════════════════════════════
    # STEP 5: Send to all Telegram channels
    # ═══════════════════════════════════════════════════════
    logger.info("📤 Sending posts...")
    results = send_daily_post_to_all(posts_by_lang)

    for lang, ok in results.items():
        status = "✅" if ok else "❌"
        logger.info("  %s %s channel", status, lang)

    if not results:
        logger.error("❌ No posts were sent")
    elif all(results.values()):
        logger.info("✅ All posts sent successfully!")

        # Save posted items to DB to avoid duplicates.
        movie_ids = []
        show_ids = []

        logger.info("💾 Saving items to database...")
        for item in enriched_items:
            title = item.get("title") or item.get("name")
            original_title = item.get("original_title") or item.get("original_name") or ""
            tmdb_id = item.get("id")
            media_type = item.get("media_type") or "movie"
            year = extract_year(item)
            poster_url = item.get("poster_url") or ""

            buzz_score = item.get("buzz_score", 0)
            tmdb_score = item.get("vote_average", 0.0)

            rating = item.get("score", 0)  # AI generated rating
            pos_comments = item.get("positive_comments", [])
            pos_comment = pos_comments[0] if pos_comments else ""
            neg_comments = item.get("negative_comments", [])
            neg_comment = neg_comments[0] if neg_comments else ""

            episodes_count = item.get("episodes_count", 0)
            parts_count = item.get("parts_count", 0)
            discussion_count = item.get("discussion_count", 0)

            # Genres is already a comma-separated string from get_genre_names().
            genres_str = item.get("genres", "")
            if isinstance(genres_str, list):
                genres_list = genres_str
            else:
                genres_list = [g.strip() for g in genres_str.split(",") if g.strip() and g.strip() != "Unknown"]

            pub_id = save_publication(
                title=title,
                media_type=media_type,
                tmdb_id=tmdb_id,
                score=buzz_score,
                genres=genres_list,
                poster_url=poster_url,
                year=year,
                original_title=original_title,
                tmdb_score=tmdb_score,
                positive_comment=pos_comment,
                negative_comment=neg_comment,
                rating=rating,
                episodes_count=episodes_count,
                parts_count=parts_count,
                is_top=True,
                discussion_count=discussion_count
            )

            if pub_id:
                logger.info("  ✅ Saved '%s' (DB ID: %s)", title, pub_id)
                if media_type == "movie":
                    movie_ids.append(pub_id)
                else:
                    show_ids.append(pub_id)

        # Save daily top
        save_daily_top(movie_ids, show_ids)
        logger.info("  ✅ Saved daily top to DB")

    else:
        logger.warning("⚠️ Some posts failed to send")


if __name__ == "__main__":
    run()
