from dotenv import load_dotenv

# Load .env at the very top.
load_dotenv()

from typing import Dict, Optional, Tuple

from ai.gemini import analyze_movie
from bot.sender import send_daily_post
from fetchers.reddit import get_top_comments, search_movie_discussion
from fetchers.tmdb import (
    get_comedy_trending,
    get_genre_names,
    get_poster_url,
    get_trending_all,
)
from formatter import build_daily_post


def extract_year(item: Dict) -> Optional[int]:
    date_str = item.get("release_date") or item.get("first_air_date")
    if not date_str:
        return None
    try:
        return int(str(date_str)[:4])
    except (ValueError, TypeError):
        return None


def select_slots(trending_list: list) -> Tuple[Dict, Dict, Dict]:
    slot1 = trending_list[0]

    slot2 = next(
        (
            item
            for item in trending_list
            if 35 in (item.get("genre_ids") or [])
            and item.get("id") != slot1.get("id")
        ),
        None,
    )
    if slot2 is None:
        comedy_list = get_comedy_trending()
        slot2 = comedy_list[0] if comedy_list else trending_list[0]

    slot3 = next(
        (
            item
            for item in trending_list
            if 35 not in (item.get("genre_ids") or [])
            and item.get("id") != slot1.get("id")
        ),
        None,
    )
    if slot3 is None:
        slot3 = trending_list[1] if len(trending_list) > 1 else trending_list[0]

    return slot1, slot2, slot3


def enrich_item(tmdb_item: Dict) -> Dict:
    title = tmdb_item.get("title") or tmdb_item.get("name")
    year = extract_year(tmdb_item)
    reddit = search_movie_discussion(title, year)
    comments = get_top_comments(reddit["comments"])
    genre_names = get_genre_names(tmdb_item.get("genre_ids", []))

    ai = analyze_movie(
        title,
        tmdb_item.get("media_type"),
        genre_names,
        tmdb_item.get("overview", ""),
        comments,
    )

    return {
        **tmdb_item,
        **ai,
        "title": title,
        "genres": genre_names,
        "poster_url": get_poster_url(tmdb_item.get("poster_path")),
    }


def run() -> None:
    print("🎬 Starting Movie Pulse Bot...")
    trending = get_trending_all()
    if not trending:
        print("❌ No trending data")
        return

    s1, s2, s3 = select_slots(trending)
    print("Slots:")
    print(f"- {s1.get('title') or s1.get('name')}")
    print(f"- {s2.get('title') or s2.get('name')}")
    print(f"- {s3.get('title') or s3.get('name')}")

    main_item = enrich_item(s1)
    comedy_item = enrich_item(s2)
    third_item = enrich_item(s3)

    post = build_daily_post(main_item, comedy_item, third_item)
    ok = send_daily_post(post["caption"], post["poster_url"])
    print("✅ Sent!" if ok else "❌ Failed")


if __name__ == "__main__":
    run()
