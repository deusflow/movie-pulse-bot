"""Smoke test — verify all fetchers can connect to their data sources."""

import os
import sys
import logging

# Ensure the project root is on the path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def test_tmdb(results):
    """Test TMDB trending endpoint."""
    from fetchers.tmdb import get_trending_all
    logger.info("\n📋 TMDB:")
    try:
        items = get_trending_all(3)
        if items:
            logger.info("  TMDB trending: %d items", len(items))
            logger.info("    First: %s", items[0].get('title'))
            results["TMDB"] = True
        else:
            logger.info("  TMDB trending: 0 items")
            results["TMDB"] = False
    except Exception as exc:
        logger.error("  ❌ ERROR: %s", exc)
        results["TMDB"] = False


def test_omdb(results):
    """Test OMDb API."""
    from fetchers.omdb import get_movie_scores
    logger.info("\n📋 OMDb:")
    try:
        scores = get_movie_scores("The Dark Knight", 2008)
        has_data = scores.get("imdb_rating") is not None
        logger.info("  OMDb: imdb=%s, rt=%s", scores.get('imdb_rating'), scores.get('rt_score'))
        results["OMDb"] = has_data
    except Exception as exc:
        logger.error("  ❌ ERROR: %s", exc)
        results["OMDb"] = False


def test_google_news(results):
    """Test Google News RSS."""
    from fetchers.google_news import get_news_buzz
    logger.info("\n📋 Google News:")
    try:
        buzz = get_news_buzz("movie", None, max_snippets=2)
        logger.info("  Google News: %d mentions", buzz.get('mention_count', 0))
        results["Google News"] = buzz.get("mention_count", 0) > 0
    except Exception as exc:
        logger.error("  ❌ ERROR: %s", exc)
        results["Google News"] = False


def test_letterboxd(results):
    """Test Letterboxd (now Movie Press RSS)."""
    from fetchers.letterboxd import get_press_mentions
    logger.info("\n📋 Letterboxd:")
    try:
        res = get_press_mentions("movie")
        logger.info("  Movie Press: %d mentions", res.get('mention_count', 0))
        results["Letterboxd"] = res.get("sources_checked", 0) > 0
    except Exception as exc:
        logger.error("  ❌ ERROR: %s", exc)
        results["Letterboxd"] = False


def test_reddit(results):
    """Test Reddit discussion fetcher (RSS-based)."""
    from fetchers.reddit import get_reddit_discussion
    logger.info("\n📋 Reddit:")
    try:
        res = get_reddit_discussion("Scary Movie", "movie", max_comments=3, max_posts=2)
        post_count = res.get("post_count", 0)
        comment_count = len(res.get("comments", []))
        sources = res.get("sources", [])
        logger.info(
            "  Reddit: %d posts, %d comments (%s)",
            post_count, comment_count, ", ".join(sources) if sources else "none",
        )
        # Pass if it ran without raising; Reddit may occasionally rate-limit.
        results["Reddit"] = True
    except Exception as exc:
        logger.error("  ❌ ERROR: %s", exc)
        results["Reddit"] = False


def test_rottentomatoes(results):
    """Test Rotten Tomatoes fetcher (graceful — may return 0 reviews)."""
    from fetchers.rottentomatoes import get_audience_reviews
    logger.info("\n📋 Rotten Tomatoes:")
    try:
        res = get_audience_reviews("Sinners", "movie", max_reviews=3)
        review_count = res.get("review_count", 0)
        has_metadata = bool(res.get("metadata", {}))
        logger.info(
            "  RT: %d reviews, metadata=%s",
            review_count, "✅" if has_metadata else "❌",
        )
        # Pass if it ran without crashing; RT may not return reviews.
        results["Rotten Tomatoes"] = True
    except Exception as exc:
        logger.error("  ❌ ERROR: %s", exc)
        results["Rotten Tomatoes"] = False


def test_youtube(results):
    """Test YouTube comments (optional — may not have API key)."""
    from fetchers.youtube_comments import get_trailer_comments
    logger.info("\n📋 YouTube:")
    if not os.getenv("YOUTUBE_API_KEY"):
        logger.info("  YouTube: SKIPPED (no API key)")
        results["YouTube"] = True
        return
    try:
        result = get_trailer_comments("Inception", 2010, max_comments=3)
        logger.info("  YouTube: %d comments", result.get('comment_count', 0))
        results["YouTube"] = True
    except Exception as exc:
        logger.error("  ❌ ERROR: %s", exc)
        results["YouTube"] = False


def test_formatter(results):
    """Test HTML formatter produces valid output."""
    from formatter import build_daily_post
    logger.info("\n📋 Formatter:")
    try:
        mock_item = {
            "title": "Test Movie",
            "media_type": "movie",
            "genres": "Action, Drama",
            "one_line_summary": "A test movie summary",
            "positive_comments": ["Great acting"],
            "negative_comments": ["Slow pacing"],
            "buzz_score": 75,
            "rt_score": 80,
            "imdb_rating": 7.5,
            "metascore": 70,
            "poster_url": "https://example.com/poster.jpg",
        }
        post = build_daily_post(mock_item, mock_item, mock_item, mock_item, "en")
        caption_len = len(post.get("text", ""))
        logger.info("  Formatter: 1 combined post generated (%d chars)", caption_len)
        logger.info("    Poster: %s", '✅' if post.get('poster_url') else '❌')
        results["Formatter"] = caption_len > 0
    except Exception as exc:
        logger.error("  ❌ ERROR: %s", exc)
        results["Formatter"] = False


def main():
    logger.info("🧪 Smoke Test\n")
    results = {}
    
    test_tmdb(results)
    test_omdb(results)
    test_google_news(results)
    test_letterboxd(results)
    test_reddit(results)
    test_rottentomatoes(results)
    test_youtube(results)
    test_formatter(results)

    logger.info("\n" + "=" * 40)
    logger.info("Results:")
    all_ok = True
    for name, ok in results.items():
        status = "✅ PASS" if ok else "❌ FAIL"
        logger.info("  %s — %s", status, name)
        if not ok:
            all_ok = False

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
