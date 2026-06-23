"""Telegram bot sender — sends movie posts to channels."""

import asyncio
import logging
import os
from typing import Dict, Optional

from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode
from telegram import LinkPreviewOptions

load_dotenv()

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Channel IDs per language.
CHANNELS = {
    "en": os.getenv("TELEGRAM_CHANNEL_ID") or os.getenv("TELEGRAM_CHANNEL_ID_EN"),
    "uk": os.getenv("TELEGRAM_CHANNEL_ID_UK"),
}


async def _send_post_to_channel(
    bot: Bot,
    channel_id: str,
    post: Dict[str, Optional[str]],
) -> bool:
    """Send a single long text message with a large poster preview."""
    try:
        text = post.get("text", "")
        poster_url = post.get("poster_url")
        
        preview_options = None
        if poster_url:
            preview_options = LinkPreviewOptions(
                url=poster_url, 
                prefer_large_media=True, 
                show_above_text=True
            )
            
        await bot.send_message(
            chat_id=channel_id,
            text=text,
            parse_mode=ParseMode.HTML,
            link_preview_options=preview_options
        )
        logger.info("  ✅ Post sent successfully")
        return True
    except Exception as exc:
        logger.error("Send failed to %s: %s", channel_id, exc)
        return False


async def _send_all(
    posts_by_lang: Dict[str, Dict[str, Optional[str]]],
) -> Dict[str, bool]:
    """Send posts to all configured channels."""
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")

    results = {}

    async with Bot(token=TELEGRAM_BOT_TOKEN) as bot:
        for lang, post in posts_by_lang.items():
            channel_id = CHANNELS.get(lang)
            if not channel_id:
                logger.info("⏭️ No channel configured for '%s', skipping", lang)
                continue

            logger.info("📤 Sending post to %s channel (%s)...", lang, channel_id)
            results[lang] = await _send_post_to_channel(bot, channel_id, post)

    return results


def send_daily_post_to_all(
    posts_by_lang: Dict[str, Dict[str, Optional[str]]],
) -> Dict[str, bool]:
    """
    Send daily movie post to all configured channels.

    Args:
        posts_by_lang: Dict mapping language code to a post dict.
            The post dict has "text" (str) and "poster_url" (str|None).

    Returns:
        Dict mapping language code to success boolean.
    """
    try:
        return asyncio.run(_send_all(posts_by_lang))
    except Exception as exc:
        message = str(exc)
        if "parse_mode" in message or "HTML" in message:
            logger.error("HTML formatting error in text")
        elif "Chat not found" in message:
            logger.error("Bot must be admin in channel")
        else:
            logger.error("Send error: %s", exc)
        return {}


# Legacy single-post sender for backward compatibility.
def send_daily_post(text: str, poster_url: Optional[str]) -> bool:
    """Send a single post (legacy interface)."""
    results = send_daily_post_to_all({"en": {"text": text, "poster_url": poster_url}})
    return results.get("en", False)


if __name__ == "__main__":
    result = send_daily_post("🧪 <b>Test</b> — bot works!", None)
    print("Sent:", result)
