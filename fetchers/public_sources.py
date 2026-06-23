"""Source aggregator — collects comments, scores, and streaming data from all sources.

Discussion sources (Reddit, RT) are prioritized over critic/API data:
comments from Reddit come FIRST so the AI sees audience discussion before
formal reviews.
"""

import logging
from typing import Dict, List, Optional

from fetchers.google_news import get_news_buzz
from fetchers.letterboxd import get_press_mentions
from fetchers.omdb import get_movie_scores
from fetchers.reddit import get_reddit_discussion
from fetchers.rottentomatoes import get_audience_reviews
from fetchers.tmdb import get_movie_reviews, get_watch_providers
from fetchers.youtube_comments import get_trailer_comments

logger = logging.getLogger(__name__)


def aggregate_comments(
    title: str,
    tmdb_id: Optional[int] = None,
    year: Optional[int] = None,
    media_type: str = "movie",
    max_per_source: int = 5,
) -> List[str]:
    """
    Collect comments/reviews from all available sources.

    Order matters — discussions come FIRST so the AI weights them higher:
        1. Reddit discussions  (real audience talk)
        2. RT audience reviews (verified viewer opinions)
        3. TMDB reviews        (community reviews)
        4. YouTube comments    (trailer reaction)
    """
    comments: List[str] = []

    # 1. Reddit discussions — highest priority, real audience discussion.
    try:
        reddit = get_reddit_discussion(
            title, media_type=media_type, max_comments=max_per_source * 2,
        )
        reddit_comments = reddit.get("comments", [])
        comments.extend(reddit_comments)
        if reddit_comments:
            logger.info(
                "    Reddit: %d comments from %d posts (%s)",
                len(reddit_comments),
                reddit.get("post_count", 0),
                ", ".join(reddit.get("sources", [])),
            )
    except Exception as exc:
        logger.warning("Reddit discussion failed for '%s': %s", title, exc)

    # 2. Rotten Tomatoes audience reviews.
    try:
        rt = get_audience_reviews(title, media_type=media_type, max_reviews=max_per_source)
        rt_comments = rt.get("comments", [])
        comments.extend(rt_comments)
        if rt_comments:
            logger.info("    RT: %d reviews", len(rt_comments))
    except Exception as exc:
        logger.debug("RT audience reviews failed for '%s': %s", title, exc)

    # 3. TMDB Reviews.
    tmdb_reviews = get_movie_reviews(tmdb_id, media_type=media_type, limit=max_per_source)
    for review in tmdb_reviews:
        text = review[:300].strip()
        if len(review) > 300:
            text += "..."
        comments.append(text)

    # 4. YouTube trailer comments.
    yt_data = get_trailer_comments(title, year, max_comments=max_per_source)
    comments.extend(yt_data.get("comments", []))

    return comments


def aggregate_scores(
    title: str,
    tmdb_item: Dict,
    year: Optional[int] = None,
) -> Dict:
    """
    Collect scores from multiple sources and compute a buzz score.

    Reddit engagement is weighted highest because discussions > critics.
    """
    # TMDB data (already available).
    tmdb_popularity = tmdb_item.get("popularity", 0) or 0
    tmdb_vote = tmdb_item.get("vote_average", 0) or 0
    media_type = tmdb_item.get("media_type", "movie")

    # OMDb data (RT, Metascore, IMDb).
    omdb = get_movie_scores(title, year)

    # Movie press RSS mentions.
    press = get_press_mentions(title)
    press_mentions = press.get("mention_count", 0)

    # Google News buzz.
    news = get_news_buzz(title, year, max_snippets=3)
    news_mentions = news.get("mention_count", 0)

    # Reddit engagement — how much is this being discussed TODAY.
    reddit_engagement = 0
    try:
        reddit = get_reddit_discussion(
            title, media_type=media_type, max_comments=0, max_posts=3,
        )
        reddit_engagement = reddit.get("post_count", 0)
    except Exception:
        pass

    # Streaming platforms.
    tmdb_id = tmdb_item.get("id")
    streaming = get_watch_providers(tmdb_id, media_type)

    # Compute weighted buzz score (0-100).
    buzz_score = _compute_buzz_score(
        tmdb_popularity=tmdb_popularity,
        tmdb_vote=tmdb_vote,
        rt_score=omdb.get("rt_score"),
        metascore=omdb.get("metascore"),
        imdb_rating=omdb.get("imdb_rating"),
        press_mentions=press_mentions,
        news_mentions=news_mentions,
        reddit_engagement=reddit_engagement,
    )

    return {
        "tmdb_popularity": tmdb_popularity,
        "tmdb_vote": tmdb_vote,
        "rt_score": omdb.get("rt_score"),
        "metascore": omdb.get("metascore"),
        "imdb_rating": omdb.get("imdb_rating"),
        "imdb_votes": omdb.get("imdb_votes"),
        "press_mention_count": press_mentions,
        "press_sources": press.get("sources_with_mentions", []),
        "news_mentions": news_mentions,
        "news_snippets": news.get("snippets", []),
        "reddit_engagement": reddit_engagement,
        "buzz_score": buzz_score,
        "omdb_poster_url": omdb.get("poster_url"),
        "streaming_platforms": streaming,
    }


def _compute_buzz_score(
    tmdb_popularity: float,
    tmdb_vote: float,
    rt_score: Optional[int],
    metascore: Optional[int],
    imdb_rating: Optional[float],
    press_mentions: int,
    news_mentions: int,
    reddit_engagement: int = 0,
) -> int:
    """
    Compute an aggregated buzz score from 0-100.

    Weights reflect the user's requirement: discussions > critics.

    Source weights (when all available):
        Reddit engagement:  0.25  — discussions matter most
        RT score:           0.15
        TMDB popularity:    0.12
        TMDB vote:          0.10
        IMDb rating:        0.10
        Metascore:          0.10
        Press mentions:     0.10
        News mentions:      0.08
    """
    scores = []
    weights = []

    # Reddit engagement — the most important signal.
    if reddit_engagement > 0:
        # 1 post = 40, 3+ posts = 70-100 (actively discussed).
        reddit_score = min(100, 30 + reddit_engagement * 25)
        scores.append(reddit_score)
        weights.append(0.25)

    # TMDB vote (0-10 → 0-100).
    if tmdb_vote > 0:
        scores.append(tmdb_vote * 10)
        weights.append(0.10)

    # TMDB popularity (normalized — 100+ is very popular).
    if tmdb_popularity > 0:
        pop_score = min(100, tmdb_popularity / 2)
        scores.append(pop_score)
        weights.append(0.12)

    # Rotten Tomatoes (already 0-100).
    if rt_score is not None:
        scores.append(rt_score)
        weights.append(0.15)

    # Metascore (already 0-100).
    if metascore is not None:
        scores.append(metascore)
        weights.append(0.10)

    # IMDb (0-10 → 0-100).
    if imdb_rating is not None:
        scores.append(imdb_rating * 10)
        weights.append(0.10)

    # Press mentions (0=none, 5+=well covered).
    if press_mentions > 0:
        press_score = min(100, 40 + press_mentions * 15)
        scores.append(press_score)
        weights.append(0.10)

    # News mentions (0=none, 50+=very buzzy).
    if news_mentions > 0:
        news_score = min(100, 20 + news_mentions * 2)
        scores.append(news_score)
        weights.append(0.08)

    if not scores:
        return 50  # No data available.

    # Normalize weights and compute weighted average.
    total_weight = sum(weights)
    weighted_sum = sum(s * w for s, w in zip(scores, weights))
    return max(0, min(100, int(weighted_sum / total_weight)))
