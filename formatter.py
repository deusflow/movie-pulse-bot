import re
from typing import Dict, Optional

MAX_CAPTION_LENGTH = 950


def escape_md(text: str) -> str:
    if text is None:
        return ""
    return re.sub(r"([_\*\[\]\(\)~`>#+\-=|{}.!])", r"\\\1", str(text))


def _media_emoji(media_type: str) -> str:
    if (media_type or "").lower() == "tv":
        return "📺"
    return "🎥"


def _score_emoji(score: int) -> str:
    if score >= 80:
        return "🔥"
    if score <= 40:
        return "💀"
    return ""


def _shorten(text: str, max_len: int) -> str:
    if text is None:
        return ""
    if len(text) <= max_len:
        return text
    return f"{text[: max_len - 3].rstrip()}..."


def _build_caption(
    main_title: str,
    main_genres: str,
    main_score: int,
    main_summary: str,
    main_positive: str,
    main_negative: str,
    comedy_title: str,
    comedy_genres: str,
    comedy_score: int,
    comedy_summary: str,
    third_title: str,
    third_genres: str,
    third_score: int,
    media_emoji: str,
    score_emoji: str,
) -> str:
    return (
        "🎬 *Daily Movie Pulse*\n"
        "──────────────\n\n"
        "🔥 *Most Discussed*\n"
        f"*{main_title}* {media_emoji}\n"
        f"• Genres: {main_genres}\n"
        f"• Score: {main_score}/100{score_emoji}\n"
        f"• _{main_summary}_\n"
        f"👍 {main_positive}\n"
        f"👎 {main_negative}\n\n"
        "😂 *Comedy Pick*\n"
        f"*{comedy_title}*\n"
        f"• Genres: {comedy_genres}\n"
        f"• Score: {comedy_score}/100\n"
        f"• _{comedy_summary}_\n\n"
        "📊 *Also Trending*\n"
        f"*{third_title}*\n"
        f"• Genres: {third_genres}\n"
        f"• Score: {third_score}/100\n\n"
        "\\#movies \\#trending \\#dailypulse"
    )


def build_daily_post(
    main_item: Dict,
    comedy_item: Dict,
    third_item: Dict,
) -> Dict[str, Optional[str]]:
    main_title = escape_md(main_item.get("title", ""))
    main_genres = escape_md(main_item.get("genres", ""))
    main_score = int(main_item.get("score", 0) or 0)
    main_summary = escape_md(main_item.get("one_line_summary", ""))
    main_positive = escape_md(main_item.get("positive_comment", ""))
    main_negative = escape_md(main_item.get("negative_comment", ""))

    comedy_title = escape_md(comedy_item.get("title", ""))
    comedy_genres = escape_md(comedy_item.get("genres", ""))
    comedy_score = int(comedy_item.get("score", 0) or 0)
    comedy_summary = escape_md(comedy_item.get("one_line_summary", ""))

    third_title = escape_md(third_item.get("title", ""))
    third_genres = escape_md(third_item.get("genres", ""))
    third_score = int(third_item.get("score", 0) or 0)

    media_emoji = _media_emoji(main_item.get("media_type", ""))
    score_emoji = _score_emoji(main_score)

    caption = _build_caption(
        main_title,
        main_genres,
        main_score,
        main_summary,
        main_positive,
        main_negative,
        comedy_title,
        comedy_genres,
        comedy_score,
        comedy_summary,
        third_title,
        third_genres,
        third_score,
        media_emoji,
        score_emoji,
    )

    if len(caption) > MAX_CAPTION_LENGTH:
        main_summary = escape_md(_shorten(main_item.get("one_line_summary", ""), 60))
        comedy_summary = escape_md(_shorten(comedy_item.get("one_line_summary", ""), 60))
        caption = _build_caption(
            main_title,
            main_genres,
            main_score,
            main_summary,
            main_positive,
            main_negative,
            comedy_title,
            comedy_genres,
            comedy_score,
            comedy_summary,
            third_title,
            third_genres,
            third_score,
            media_emoji,
            score_emoji,
        )

    return {
        "caption": caption,
        "poster_url": main_item.get("poster_url"),
    }
