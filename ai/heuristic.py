from typing import Dict, List

POSITIVE_WORDS = {
    "great",
    "amazing",
    "excellent",
    "good",
    "love",
    "loved",
    "awesome",
    "fun",
    "fantastic",
    "brilliant",
    "masterpiece",
    "solid",
}

NEGATIVE_WORDS = {
    "bad",
    "boring",
    "awful",
    "terrible",
    "hate",
    "hated",
    "slow",
    "worse",
    "worst",
    "disappointing",
    "mess",
    "weak",
}

DEFAULT_RESULT = {
    "score": 50,
    "positive_comment": "Not enough data",
    "negative_comment": "Not enough data",
    "one_line_summary": "Currently trending",
}


def _count_keywords(text: str, keywords: set[str]) -> int:
    lowered = text.lower()
    return sum(1 for word in keywords if word in lowered)


def analyze_movie_offline(
    title: str,
    media_type: str,
    genres: str,
    overview: str,
    comments: List[str],
) -> Dict:
    if not comments:
        return DEFAULT_RESULT

    positive_comment = next(
        (c for c in comments if _count_keywords(c, POSITIVE_WORDS) > 0),
        "Mixed reactions",
    )
    negative_comment = next(
        (c for c in comments if _count_keywords(c, NEGATIVE_WORDS) > 0),
        "Mixed reactions",
    )

    pos = sum(_count_keywords(c, POSITIVE_WORDS) for c in comments)
    neg = sum(_count_keywords(c, NEGATIVE_WORDS) for c in comments)
    score = 50 + (pos - neg) * 7
    score = max(0, min(100, score))

    one_line_summary = "Mixed sentiment from public comments"
    if pos > neg + 2:
        one_line_summary = "Positive buzz from public comments"
    elif neg > pos + 2:
        one_line_summary = "Negative buzz from public comments"

    return {
        "score": score,
        "positive_comment": positive_comment[:120],
        "negative_comment": negative_comment[:120],
        "one_line_summary": one_line_summary[:100],
    }

