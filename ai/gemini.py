import json
import os
import re
from typing import Dict, List

from dotenv import load_dotenv
from groq import Groq
from ai.heuristic import analyze_movie_offline

# Load environment variables once at import time.
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY")
DEFAULT_RESULT = {
    "score": 50,
    "positive_comment": "Not enough data",
    "negative_comment": "Not enough data",
    "one_line_summary": "Currently trending",
}


def _strip_fences(text: str) -> str:
    if not text:
        return ""
    stripped = text.strip()
    # Remove ```json or ``` fences if present.
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def analyze_movie(
    title: str,
    media_type: str,
    genres: str,
    overview: str,
    comments: List[str],
) -> Dict:
    if not comments:
        return DEFAULT_RESULT

    if not GROQ_API_KEY:
        print("GROQ_API_KEY is missing. Using offline heuristic analyzer")
        return analyze_movie_offline(title, media_type, genres, overview, comments)

    prompt = (
        "You are a movie sentiment analyst. Respond ONLY with JSON in this format: "
        "{\"score\": <0-100>, \"positive_comment\": \"<120 chars>\", "
        "\"negative_comment\": \"<120 chars>\", \"one_line_summary\": \"<100 chars>\"}. "
        "Use this score guide: 0-30=terrible, 31-50=disappointing, 51-65=average, "
        "66-79=good, 80-90=great, 91-100=masterpiece. "
        f"Title: {title}. Media type: {media_type}. Genres: {genres}. "
        f"Overview: {overview}. Comments: {comments}."
    )

    try:
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_completion_tokens=1024,
            stream=False,
        )
        result = response.choices[0].message.content
    except Exception as exc:
        print(f"Groq API error: {exc}")
        return analyze_movie_offline(title, media_type, genres, overview, comments)

    try:
        raw_text = _strip_fences(result or "")
        return json.loads(raw_text)
    except Exception as exc:
        print(f"Groq response parse error: {exc}")
        return analyze_movie_offline(title, media_type, genres, overview, comments)


if __name__ == "__main__":
    r = analyze_movie(
        "Sinners",
        "movie",
        "Horror",
        "A period horror film",
        ["Best horror in years", "Too slow", "Coogler outdid himself"],
    )
    print(r)
