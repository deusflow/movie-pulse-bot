"""AI movie analyzer — Gemini for sentiment analysis, summarization, and top picks.

Two main functions:
    pick_top_from_discussions() — NEW: single AI call to pick Top 2 movies + Top 2 series
                                  from aggregated discussions across all sources.
    analyze_movie()            — LEGACY: per-item analysis (kept as fallback).
"""

import json
import logging
import os
import time
from typing import Dict, List, Optional

from dotenv import load_dotenv

try:
    from ai.heuristic import analyze_movie_offline
except ModuleNotFoundError:
    from heuristic import analyze_movie_offline

load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

DEFAULT_RESULT = {
    "score": 50,
    "positive_comments": [],
    "negative_comments": [],
    "one_line_summary": "Currently trending",
    "relevance": "medium",
}

DEFAULT_TOP_PICK = {
    "title": "Unknown",
    "media_type": "movie",
    "score": 50,
    "positive_comment": "",
    "negative_comment": "",
    "one_line_summary": "Currently trending",
}


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------
def _call_gemini_with_retry(client, model: str, prompt: str, config, max_retries: int = 4) -> Optional[str]:
    """
    Call Gemini API with smart retry logic.

    Free tier limits:
        - 5 requests per minute for gemini-3.5-flash
        - 429 RESOURCE_EXHAUSTED → wait 30 seconds (API suggests ~25s)
        - 503 UNAVAILABLE → exponential backoff: 5s, 10s, 20s, 40s
    """
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )
            return response.text
        except Exception as e:
            error_str = str(e)
            logger.warning("Gemini API attempt %d/%d failed: %s", attempt + 1, max_retries, e)

            if attempt >= max_retries - 1:
                raise

            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                # Free tier quota exhausted — API says wait ~25s
                wait_time = 30
                logger.info("⏳ Rate limited (429). Waiting %d seconds...", wait_time)
                time.sleep(wait_time)
            elif "503" in error_str or "UNAVAILABLE" in error_str:
                # Server overloaded — exponential backoff
                wait_time = 5 * (2 ** attempt)  # 5, 10, 20, 40
                logger.info("⏳ Server unavailable (503). Waiting %d seconds...", wait_time)
                time.sleep(wait_time)
            else:
                # Unknown error — don't retry
                raise

    return None


# ---------------------------------------------------------------------------
# NEW: Pick top from discussions (SINGLE AI call)
# ---------------------------------------------------------------------------
def pick_top_from_discussions(
    discussions: List[Dict],
    lang: str = "en",
) -> List[Dict]:
    """
    Analyze ALL collected discussions and pick Top 2 movies + Top 2 series.

    This replaces the old approach of 4 separate AI calls.
    ONE call to Gemini analyzes 30-80 discussion items and returns
    structured picks with sentiment analysis.

    Args:
        discussions: List of discussion items from discover_discussions().
        lang: Language code for output.

    Returns:
        List of 4 dicts: [movie1, series1, movie2, series2]
        Each dict has: title, media_type, score, positive_comment,
                       negative_comment, one_line_summary
    """
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY missing — cannot pick top from discussions")
        return _fallback_picks(discussions)

    # Language instruction.
    lang_instruction = "Write all text in English."
    if lang == "uk":
        lang_instruction = (
            "Write all text in Ukrainian (Українська мова). "
            "Keep movie/show titles in their original English form."
        )

    # Build the discussion summary for AI.
    discussion_text = _format_discussions_for_ai(discussions)

    prompt = (
        "You are a movie/TV trend analyst. Below is a collection of TODAY's discussions "
        "about movies and TV shows from multiple sources: Reddit, YouTube, Google News, "
        "film press (Variety, Hollywood Reporter), and TMDB trending.\n\n"
        "Your task: analyze ALL these discussions and pick:\n"
        "- TOP 2 MOVIES that people are discussing the most today\n"
        "- TOP 2 TV SERIES that people are discussing the most today\n\n"
        "Respond ONLY with valid JSON (no markdown, no explanation) in this exact format:\n"
        "{\n"
        '  "picks": [\n'
        '    {"title": "<exact movie title>", "media_type": "movie", "score": <0-100>, '
        '"positive_comment": "<what people like, max 120 chars>", '
        '"negative_comment": "<what people dislike, max 120 chars>", '
        '"one_line_summary": "<why it\'s trending, max 120 chars>"},\n'
        '    {"title": "<exact series title>", "media_type": "tv", ...},\n'
        '    {"title": "<second movie>", "media_type": "movie", ...},\n'
        '    {"title": "<second series>", "media_type": "tv", ...}\n'
        "  ]\n"
        "}\n\n"
        "RULES:\n"
        "- Pick items that appear MOST FREQUENTLY across different sources\n"
        "- Items mentioned on Reddit AND in news = very hot\n"
        "- Score 0-100 reflects public sentiment (80+ = loved, 50 = mixed, 30 = hated)\n"
        "- Comments MUST sound like REAL human opinions, casual and conversational\n"
        "- Example good: \"The chemistry between the leads is fire, honestly\"\n"
        "- Example bad: \"This film excels in character development\" (too formal)\n"
        "- one_line_summary should explain WHY it's being discussed today\n"
        "- MUST return exactly 2 movies and 2 TV series\n"
        "- Use EXACT titles as they appear in the discussions\n\n"
        f"LANGUAGE: {lang_instruction}\n\n"
        f"=== TODAY'S DISCUSSIONS ({len(discussions)} items) ===\n"
        f"{discussion_text}\n"
    )

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.4,
        )

        raw = _call_gemini_with_retry(client, GEMINI_MODEL, prompt, config)

        if not raw:
            logger.error("Gemini returned empty response for top picks")
            return _fallback_picks(discussions)

        parsed = json.loads(raw)
        picks = parsed.get("picks", [])

        if len(picks) < 4:
            logger.warning("Gemini returned only %d picks (expected 4)", len(picks))
            # Pad with defaults if needed
            while len(picks) < 4:
                picks.append(DEFAULT_TOP_PICK.copy())

        # Validate each pick
        validated = []
        for pick in picks[:4]:
            validated.append({
                "title": str(pick.get("title", "Unknown")),
                "media_type": str(pick.get("media_type", "movie")),
                "score": max(0, min(100, int(pick.get("score", 50) or 50))),
                "positive_comment": str(pick.get("positive_comment", ""))[:120],
                "negative_comment": str(pick.get("negative_comment", ""))[:120],
                "one_line_summary": str(pick.get("one_line_summary", "Currently trending"))[:120],
            })

        # Ensure we have exactly 2 movies and 2 series
        movies = [p for p in validated if p["media_type"] == "movie"]
        series = [p for p in validated if p["media_type"] == "tv"]

        # Reorder: movie1, series1, movie2, series2
        result = []
        result.append(movies[0] if len(movies) > 0 else validated[0])
        result.append(series[0] if len(series) > 0 else validated[1])
        result.append(movies[1] if len(movies) > 1 else validated[2])
        result.append(series[1] if len(series) > 1 else validated[3])

        logger.info("🤖 AI picked: %s", ", ".join(p["title"] for p in result))
        return result

    except json.JSONDecodeError as exc:
        logger.error("Gemini response parse error: %s", exc)
        return _fallback_picks(discussions)
    except Exception as exc:
        logger.error("Gemini API error for top picks: %s", exc)
        return _fallback_picks(discussions)


def _format_discussions_for_ai(discussions: List[Dict]) -> str:
    """Format discussion items into a compact text block for AI prompt."""
    lines = []
    for i, item in enumerate(discussions[:80], 1):
        source = item.get("source", "unknown")
        context = item.get("context", item.get("title_raw", ""))[:200]
        hint = item.get("media_hint", "")
        hint_str = f" [{hint}]" if hint else ""
        lines.append(f"{i}. [{source}]{hint_str} {context}")
    return "\n".join(lines)


def _fallback_picks(discussions: List[Dict]) -> List[Dict]:
    """
    Fallback when AI is unavailable: pick items from TMDB trending data
    that also appear in discussions (if possible).
    """
    logger.warning("Using fallback picks (no AI available)")

    # Try to find TMDB items in discussions
    tmdb_items = [d for d in discussions if d.get("source") == "tmdb_trending" and d.get("tmdb_data")]
    movies = [d for d in tmdb_items if d.get("media_hint") == "movie"]
    series = [d for d in tmdb_items if d.get("media_hint") == "tv"]

    picks = []

    # Movie 1
    if movies:
        m = movies[0]
        picks.append({
            "title": m["title_raw"],
            "media_type": "movie",
            "score": 50,
            "positive_comment": "",
            "negative_comment": "",
            "one_line_summary": "Trending on TMDB",
        })
    else:
        picks.append(DEFAULT_TOP_PICK.copy())

    # Series 1
    if series:
        s = series[0]
        picks.append({
            "title": s["title_raw"],
            "media_type": "tv",
            "score": 50,
            "positive_comment": "",
            "negative_comment": "",
            "one_line_summary": "Trending on TMDB",
        })
    else:
        p = DEFAULT_TOP_PICK.copy()
        p["media_type"] = "tv"
        picks.append(p)

    # Movie 2
    if len(movies) > 1:
        m = movies[1]
        picks.append({
            "title": m["title_raw"],
            "media_type": "movie",
            "score": 50,
            "positive_comment": "",
            "negative_comment": "",
            "one_line_summary": "Trending on TMDB",
        })
    else:
        picks.append(DEFAULT_TOP_PICK.copy())

    # Series 2
    if len(series) > 1:
        s = series[1]
        picks.append({
            "title": s["title_raw"],
            "media_type": "tv",
            "score": 50,
            "positive_comment": "",
            "negative_comment": "",
            "one_line_summary": "Trending on TMDB",
        })
    else:
        p = DEFAULT_TOP_PICK.copy()
        p["media_type"] = "tv"
        picks.append(p)

    return picks


# ---------------------------------------------------------------------------
# Validation helper (used by both functions)
# ---------------------------------------------------------------------------
def _validate_result(data: Dict) -> Dict:
    """Ensure the AI result has all expected keys with correct types."""
    result = {}

    result["score"] = max(0, min(100, int(data.get("score", 50) or 50)))

    # Positive comment — expect a single string, wrap in list for compatibility.
    pos = data.get("positive_comment", "") or data.get("positive_comments", "")
    if isinstance(pos, list):
        pos = pos[0] if pos else ""
    result["positive_comments"] = [str(pos)[:120]] if pos else []

    # Negative comment — expect a single string, wrap in list for compatibility.
    neg = data.get("negative_comment", "") or data.get("negative_comments", "")
    if isinstance(neg, list):
        neg = neg[0] if neg else ""
    result["negative_comments"] = [str(neg)[:120]] if neg else []

    result["one_line_summary"] = str(data.get("one_line_summary", "Currently trending"))[:120]
    result["relevance"] = str(data.get("relevance", "medium"))

    return result


# ---------------------------------------------------------------------------
# LEGACY: Per-item analysis (kept as fallback)
# ---------------------------------------------------------------------------
def analyze_movie(
    title: str,
    media_type: str,
    genres: str,
    overview: str,
    comments: List[str],
    lang: str = "en",
) -> Dict:
    """
    Analyze a movie using AI and return structured sentiment data.
    LEGACY — kept for backward compatibility and fallback scenarios.
    """
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY is missing. Using offline heuristic analyzer")
        if comments:
            return analyze_movie_offline(title, media_type, genres, overview, comments)
        return DEFAULT_RESULT.copy()

    # Language instruction.
    lang_instruction = "Write all text in English."
    if lang == "uk":
        lang_instruction = (
            "Write all text in Ukrainian (Українська мова). "
            "Translate movie descriptions and comments to Ukrainian. "
            "Keep the movie title in its original English form."
        )

    prompt = (
        "You are a movie/TV sentiment analyst. Analyze the following content and respond "
        "ONLY with valid JSON (no markdown, no explanation) in this exact format:\n"
        "{\n"
        '  "score": <0-100>,\n'
        '  "positive_comment": "<what most people liked, max 120 chars>",\n'
        '  "negative_comment": "<what most people disliked, max 120 chars>",\n'
        '  "one_line_summary": "<concise description, max 120 chars>",\n'
        '  "relevance": "<high|medium|low>"\n'
        "}\n\n"
        "Score guide: 0-30=terrible, 31-50=disappointing, 51-65=average, "
        "66-79=good, 80-90=great, 91-100=masterpiece.\n\n"
        "RULES for comments:\n"
        "- From ALL the user reviews provided, synthesize ONE positive comment "
        "that represents what MOST people liked (max 120 chars).\n"
        "- Synthesize ONE negative comment that represents what MOST people "
        "disliked (max 120 chars).\n"
        "- These MUST sound like REAL human opinions, NOT AI summaries.\n"
        "- Use casual, conversational language — as if a real person wrote it.\n"
        "- Example good: \"The chemistry between the leads is fire, honestly\"\n"
        "- Example bad: \"This film excels in its character development\" (too formal)\n"
        "- If no reviews are provided, generate plausible comments based on "
        "the overview and genres.\n\n"
        f"LANGUAGE: {lang_instruction}\n\n"
        f"Title: {title}\n"
        f"Media type: {media_type}\n"
        f"Genres: {genres}\n"
        f"Overview: {overview}\n"
    )

    if comments:
        prompt += "User reviews from multiple sources:\n"
        for i, comment in enumerate(comments[:15], 1):
            prompt += f"  {i}. {comment[:300]}\n"
    else:
        prompt += "No user reviews available — analyze based on overview and genres.\n"

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.3,
        )

        raw = _call_gemini_with_retry(client, GEMINI_MODEL, prompt, config)
    except Exception as exc:
        logger.error("Gemini API error after retries: %s", exc)
        if comments:
            return analyze_movie_offline(title, media_type, genres, overview, comments)
        return DEFAULT_RESULT.copy()

    try:
        parsed = json.loads(raw or "")
        return _validate_result(parsed)
    except Exception as exc:
        logger.error("Gemini response parse error: %s", exc)
        if comments:
            return analyze_movie_offline(title, media_type, genres, overview, comments)
        return DEFAULT_RESULT.copy()


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    r = analyze_movie(
        "Sinners",
        "movie",
        "Horror",
        "A period horror film",
        ["Best horror in years", "Too slow", "Coogler outdid himself"],
    )
    print(json.dumps(r, indent=2))
