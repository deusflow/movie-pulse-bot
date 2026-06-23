"""Offline heuristic movie analyzer — fallback when AI is unavailable."""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

POSITIVE_WORDS = {
    "great", "amazing", "excellent", "good", "love", "loved", "awesome",
    "fun", "fantastic", "brilliant", "masterpiece", "solid", "beautiful",
    "perfect", "incredible", "outstanding", "superb", "wonderful",
    "hilarious", "thrilling", "stunning", "best",
}

NEGATIVE_WORDS = {
    "bad", "boring", "awful", "terrible", "hate", "hated", "slow",
    "worse", "worst", "disappointing", "mess", "weak", "generic",
    "predictable", "overrated", "mediocre", "dull", "forgettable",
    "cringe", "pointless", "waste",
}

DEFAULT_RESULT = {
    "score": 50,
    "positive_comments": [],
    "negative_comments": [],
    "one_line_summary": "Currently trending",
    "relevance": "medium",
}


def _count_keywords(text: str, keywords: set[str]) -> int:
    """Count how many keyword matches appear in the text."""
    import re
    words = set(re.findall(r"\b\w+\b", text.lower()))
    return sum(1 for word in keywords if word in words)


def _find_best_comment(comments: List[str], keywords: set[str]) -> List[str]:
    """Find up to 2 comments that best match the given keywords."""
    scored = []
    for c in comments:
        score = _count_keywords(c, keywords)
        if score > 0:
            scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c[:120] for _, c in scored[:2]]


def analyze_movie_offline(
    title: str,
    media_type: str,
    genres: str,
    overview: str,
    comments: List[str],
) -> Dict:
    """
    Analyze movie sentiment using simple keyword heuristics.

    Returns the same structure as the AI analyzer.
    """
    if not comments:
        return DEFAULT_RESULT.copy()

    positive_comments = _find_best_comment(comments, POSITIVE_WORDS)
    negative_comments = _find_best_comment(comments, NEGATIVE_WORDS)

    pos = sum(_count_keywords(c, POSITIVE_WORDS) for c in comments)
    neg = sum(_count_keywords(c, NEGATIVE_WORDS) for c in comments)
    score = 50 + (pos - neg) * 7
    score = max(0, min(100, score))

    if pos > neg + 2:
        summary = "Positive buzz from audience reviews"
    elif neg > pos + 2:
        summary = "Mixed-to-negative reception from viewers"
    else:
        summary = "Mixed sentiment from public reviews"

    return {
        "score": score,
        "positive_comments": positive_comments,
        "negative_comments": negative_comments,
        "one_line_summary": summary[:120],
        "relevance": "medium",
    }
