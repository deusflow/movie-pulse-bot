"""Telegram message formatter — builds rich HTML-formatted posts for daily digest."""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from locales import get_strings

logger = logging.getLogger(__name__)

# Telegram message length limit.
TELEGRAM_MAX_LENGTH = 4096


def _escape_html(text: str) -> str:
    """Escape HTML special characters in text."""
    if text is None:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _score_emoji(score: int) -> str:
    """Return a color emoji based on score value."""
    if score >= 85:
        return "🟢"
    if score >= 70:
        return "🟡"
    if score >= 50:
        return "🟠"
    return "🔴"


def _media_emoji(media_type: str) -> str:
    """Return emoji for media type."""
    return "📺" if (media_type or "").lower() == "tv" else "🎬"


def _build_scores_line(item: Dict) -> str:
    """Build a compact multi-source scores line with emojis."""
    parts = []

    buzz = item.get("buzz_score")
    if buzz is not None:
        parts.append(f"{_score_emoji(buzz)} {buzz}")

    rt = item.get("rt_score")
    if rt is not None:
        parts.append(f"🍅 {rt}%")

    imdb = item.get("imdb_rating")
    if imdb is not None:
        parts.append(f"⭐ {imdb}")

    meta = item.get("metascore")
    if meta is not None:
        parts.append(f"Ⓜ️ {meta}")

    return " · ".join(parts) if parts else ""


def _build_streaming_line(item: Dict) -> str:
    """Build a streaming platforms line."""
    platforms = item.get("streaming_platforms", [])
    if not platforms:
        return ""
    return "📡 " + ", ".join(platforms)


def _build_comments_block(
    positive_comments: List[str],
    negative_comments: List[str],
    strings: Dict[str, str],
) -> str:
    """Build the positive/negative comments section."""
    lines = []

    if positive_comments:
        comment = _escape_html(positive_comments[0])
        lines.append(f'  👍 <i>"{comment}"</i>')

    if negative_comments:
        comment = _escape_html(negative_comments[0])
        lines.append(f'  👎 <i>"{comment}"</i>')

    return "\n".join(lines)


def _extract_year(item: Dict) -> str:
    """Extract year string from item for display."""
    date_str = item.get("release_date") or item.get("first_air_date")
    if date_str:
        try:
            return str(date_str)[:4]
        except (ValueError, TypeError):
            pass
    return ""


def build_movie_caption(
    item: Dict,
    section_title: str,
    strings: Dict[str, str],
    include_comments: bool = True,
    include_hashtags: bool = True,
) -> str:
    """
    Build an HTML caption for a single movie/show block.

    Args:
        item: Enriched movie dict with all data.
        section_title: Localized section header.
        strings: Locale strings dict.
        include_comments: Whether to include the comments block.
        include_hashtags: Whether to include hashtags at the bottom.

    Returns:
        HTML-formatted caption string.
    """
    title = _escape_html(item.get("title", "Unknown"))
    genres = _escape_html(item.get("genres", ""))
    summary = _escape_html(item.get("one_line_summary", ""))
    media = _media_emoji(item.get("media_type", ""))
    year = _extract_year(item)

    # Section header.
    parts = [
        f"<b>{section_title}</b>",
        "",
    ]

    # Title with year.
    title_line = f"{media} <b>{title}</b>"
    if year:
        title_line += f" ({year})"
    parts.append(title_line)

    # Genres line.
    if genres and genres != "Unknown":
        parts.append(f"🏷 <i>{genres}</i>")

    # Streaming platforms.
    streaming_line = _build_streaming_line(item)
    if streaming_line:
        parts.append(streaming_line)

    # Scores line.
    scores_line = _build_scores_line(item)
    if scores_line:
        parts.append("")
        parts.append(scores_line)

    # Summary.
    if summary:
        parts.append("")
        parts.append(f"📝 {summary}")

    # Comments.
    if include_comments:
        pos = item.get("positive_comments", [])
        neg = item.get("negative_comments", [])
        if pos or neg:
            parts.append("")
            parts.append(f"💬 <b>{strings.get('comments_header', 'What people say')}:</b>")
            parts.append(_build_comments_block(pos, neg, strings))

    # Hashtags.
    if include_hashtags:
        parts.append("")
        parts.append(strings.get("hashtags", "#movies #trending"))

    return "\n".join(parts)


def build_daily_post(
    movie_item: Dict,
    tv_item: Dict,
    movie2_item: Dict,
    tv2_item: Dict,
    lang: str = "en",
) -> Dict[str, Optional[str]]:
    """
    Build a single post dict combining all four items.

    Automatically trims content if it exceeds Telegram's 4096 char limit.

    Args:
        movie_item: First movie (top trending).
        tv_item: First TV series (top trending).
        movie2_item: Second movie.
        tv2_item: Second TV series.
        lang: Language code.

    Returns:
        Dict with keys:
            text: str            — combined HTML-formatted text
            poster_url: str|None — main movie poster image URL
    """
    strings = get_strings(lang)

    # Post header with date.
    date_format = strings.get("date_format", "%B %d, %Y")
    today = datetime.now().strftime(date_format)
    header = f"{'━' * 16}\n{strings.get('header', '🎬 Daily Movie Pulse')}\n📅 {today}\n{'━' * 16}"
    separator = f"\n{'━' * 16}\n"

    parts = [header]

    # Movie #1
    parts.append("")
    parts.append(build_movie_caption(
        movie_item,
        strings.get("trending_movie_1", "🔥 TOP MOVIE"),
        strings,
        include_hashtags=False,
    ))
    parts.append(separator)

    # Series #1
    parts.append(build_movie_caption(
        tv_item,
        strings.get("trending_tv_1", "📺 TOP SERIES"),
        strings,
        include_hashtags=False,
    ))
    parts.append(separator)

    # Movie #2
    parts.append(build_movie_caption(
        movie2_item,
        strings.get("trending_movie_2", "🎬 HOT MOVIE"),
        strings,
        include_hashtags=False,
    ))
    parts.append(separator)

    # Series #2
    parts.append(build_movie_caption(
        tv2_item,
        strings.get("trending_tv_2", "🍿 HOT SERIES"),
        strings,
        include_hashtags=True,
    ))

    text = "\n".join(parts)

    # Safety: trim if exceeds Telegram limit.
    if len(text) > TELEGRAM_MAX_LENGTH:
        logger.warning(
            "Post length %d exceeds Telegram limit %d, trimming comments",
            len(text), TELEGRAM_MAX_LENGTH,
        )
        # Rebuild without comments on slots 3-4 to save space.
        parts_trimmed = [header]
        parts_trimmed.append("")
        parts_trimmed.append(build_movie_caption(
            movie_item, strings.get("trending_movie_1", "🔥 TOP MOVIE"),
            strings, include_hashtags=False,
        ))
        parts_trimmed.append(separator)
        parts_trimmed.append(build_movie_caption(
            tv_item, strings.get("trending_tv_1", "📺 TOP SERIES"),
            strings, include_hashtags=False,
        ))
        parts_trimmed.append(separator)
        parts_trimmed.append(build_movie_caption(
            movie2_item, strings.get("trending_movie_2", "🎬 HOT MOVIE"),
            strings, include_comments=False, include_hashtags=False,
        ))
        parts_trimmed.append(separator)
        parts_trimmed.append(build_movie_caption(
            tv2_item, strings.get("trending_tv_2", "🍿 HOT SERIES"),
            strings, include_comments=False, include_hashtags=True,
        ))
        text = "\n".join(parts_trimmed)

    # Final safety: hard truncate if still too long.
    if len(text) > TELEGRAM_MAX_LENGTH:
        text = text[:TELEGRAM_MAX_LENGTH - 3] + "..."
        logger.warning("Post still too long after trimming, hard truncated")

    return {
        "text": text,
        "poster_url": movie_item.get("poster_url"),
    }
