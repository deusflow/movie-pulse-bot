import asyncio
import os

from dotenv import load_dotenv
from telegram import Bot

# Load environment variables once at import time.
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")


async def _send(caption: str, poster_url: str | None) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID")

    async with Bot(token=TELEGRAM_BOT_TOKEN) as bot:
        if poster_url:
            await bot.send_photo(
                chat_id=TELEGRAM_CHANNEL_ID,
                photo=poster_url,
                caption=caption,
                parse_mode="MarkdownV2",
            )
        else:
            await bot.send_message(
                chat_id=TELEGRAM_CHANNEL_ID,
                text=caption,
                parse_mode="MarkdownV2",
            )


def send_daily_post(caption: str, poster_url: str | None) -> bool:
    try:
        asyncio.run(_send(caption, poster_url))
        return True
    except Exception as exc:
        message = str(exc)
        if "parse_mode" in message:
            print("Hint: Markdown escaping error in caption")
        elif "Chat not found" in message:
            print("Hint: Bot must be admin in channel")
        else:
            print(f"Error: {exc}")
        return False


if __name__ == "__main__":
    result = send_daily_post("🧪 *Test* \\- bot works\\!", None)
    print("Sent:", result)
