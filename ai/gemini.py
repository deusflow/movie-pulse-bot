import json
import os
import re
from typing import Dict, List

from dotenv import load_dotenv
from google import genai

# Load environment variables once at import time.
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
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

    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY is missing. Set it in .env")
        return DEFAULT_RESULT

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
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
        )
    except Exception as exc:
        print(f"Gemini API error: {exc}")
        return DEFAULT_RESULT

    try:
        raw_text = _strip_fences(getattr(response, "text", ""))
        return json.loads(raw_text)
    except Exception as exc:
        print(f"Gemini response parse error: {exc}")
        return DEFAULT_RESULT


if __name__ == "__main__":
    r = analyze_movie(
        "Sinners",
        "movie",
        "Horror",
        "A period horror film",
        ["Best horror in years", "Too slow", "Coogler outdid himself"],
    )
    print(r)
