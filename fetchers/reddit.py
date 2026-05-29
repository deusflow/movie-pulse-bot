import os
from typing import Dict, List, Optional

import praw
from dotenv import load_dotenv

# Load environment variables once at import time.
load_dotenv()

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
USER_AGENT = "MoviePulseBot/1.0"


def _get_reddit_client() -> Optional[praw.Reddit]:
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        print("Reddit credentials are missing. Set them in .env")
        return None

    try:
        return praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=USER_AGENT,
        )
    except Exception as exc:
        print(f"PRAW init failed: {exc}")
        return None


def _clean_comment(body: str) -> Optional[str]:
    if not body:
        return None

    text = body.replace("\n", " ").strip()
    if len(text) < 15:
        return None
    if text.lower() in {"[deleted]", "[removed]"}:
        return None
    return text


def search_movie_discussion(title: str, year: Optional[int] = None) -> Dict:
    result = {"title": title, "total_posts_found": 0, "comments": []}

    try:
        reddit = _get_reddit_client()
        if not reddit:
            return result

        query = f"{title} {year}" if year else title
        comments: List[str] = []
        post_count = 0

        for subreddit in ("movies", "television"):
            try:
                submissions = reddit.subreddit(subreddit).search(
                    query,
                    time_filter="month",
                    limit=5,
                )
            except Exception as exc:
                print(f"Reddit search failed for r/{subreddit}: {exc}")
                continue

            for submission in submissions:
                post_count += 1
                try:
                    submission.comments.replace_more(limit=0)
                    for comment in submission.comments[:10]:
                        if comment.author and str(comment.author) == "AutoModerator":
                            continue
                        cleaned = _clean_comment(comment.body)
                        if cleaned:
                            comments.append(cleaned)
                except Exception as exc:
                    print(f"Comment fetch failed: {exc}")
                    continue

        result["total_posts_found"] = post_count
        result["comments"] = comments
        return result
    except Exception as exc:
        print(f"Reddit fetch error: {exc}")
        return {"title": title, "total_posts_found": 0, "comments": []}


def get_top_comments(comments_list: List[str], max_comments: int = 8) -> List[str]:
    try:
        trimmed = []
        for comment in comments_list[:max_comments]:
            text = comment.replace("\n", " ").strip()
            if len(text) > 220:
                text = f"{text[:217]}..."
            trimmed.append(text)
        return trimmed
    except Exception as exc:
        print(f"Comment trim error: {exc}")
        return []


if __name__ == "__main__":
    r = search_movie_discussion("Sinners", 2025)
    print(f"Posts: {r['total_posts_found']}, Comments: {len(r['comments'])}")
    for c in r["comments"][:3]:
        print(f"  > {c[:100]}")
