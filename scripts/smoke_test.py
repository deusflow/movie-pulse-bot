import os
import sys

# Allow running from the scripts/ directory.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from formatter import build_daily_post


def main() -> None:
    sample = {
        "title": "Sample Movie",
        "media_type": "movie",
        "genres": "Action, Comedy",
        "score": 78,
        "positive_comment": "A fun crowd-pleaser",
        "negative_comment": "Some pacing issues",
        "one_line_summary": "A fast-paced action comedy with big set pieces.",
        "poster_url": None,
    }

    post = build_daily_post(sample, sample, sample)
    print("Caption length:", len(post["caption"]))
    print(post["caption"])


if __name__ == "__main__":
    main()
