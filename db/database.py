"""Database layer for publication tracking and genre relationships."""

import logging

import os
from typing import List, Dict, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

# Combined TMDB genres list for seeding
TMDB_GENRES = [
    "Action", "Adventure", "Animation", "Comedy", "Crime", 
    "Documentary", "Drama", "Family", "Fantasy", "History", 
    "Horror", "Music", "Mystery", "Romance", "Science Fiction", 
    "TV Movie", "Thriller", "War", "Western",
    "Action & Adventure", "Kids", "News", "Reality", 
    "Sci-Fi & Fantasy", "Soap", "Talk", "War & Politics"
]

def connect():
    """Connect to the PostgreSQL database."""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL is not set in the environment")
    return psycopg2.connect(url, cursor_factory=RealDictCursor)


def init_db() -> None:
    """Initialize the database schema and seed genres."""
    if not os.getenv("DATABASE_URL"):
        logger.info("DATABASE_URL not set, skipping DB initialization")
        return

    try:
        with connect() as conn:
            with conn.cursor() as cur:
                # 1. Create publications table
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS publications (
                        id SERIAL PRIMARY KEY,
                        title VARCHAR(255) NOT NULL,
                        original_title VARCHAR(255),
                        media_type VARCHAR(10),
                        tmdb_id INTEGER,
                        posted_at TIMESTAMP DEFAULT NOW(),
                        score INTEGER,
                        tmdb_score FLOAT,
                        genres TEXT[],
                        poster_url TEXT,
                        year INTEGER,
                        positive_comment TEXT,
                        negative_comment TEXT,
                        rating INTEGER,
                        episodes_count INTEGER,
                        parts_count INTEGER,
                        is_top BOOLEAN DEFAULT FALSE,
                        discussion_count INTEGER,
                        UNIQUE(tmdb_id, media_type)
                    )
                    """
                )
                
                # Create daily_top table
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS daily_top (
                        id SERIAL PRIMARY KEY,
                        date DATE UNIQUE,
                        top_movie_1_id INTEGER REFERENCES publications(id),
                        top_movie_2_id INTEGER REFERENCES publications(id),
                        top_show_1_id INTEGER REFERENCES publications(id),
                        top_show_2_id INTEGER REFERENCES publications(id),
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                    """
                )
                
                # 2. Create genres table
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS genres (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100) UNIQUE
                    )
                    """
                )
                
                # 3. Create publication_genres table
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS publication_genres (
                        publication_id INTEGER REFERENCES publications(id) ON DELETE CASCADE,
                        genre_id INTEGER REFERENCES genres(id) ON DELETE CASCADE,
                        PRIMARY KEY (publication_id, genre_id)
                    )
                    """
                )

                # Seed genres
                for genre_name in set(TMDB_GENRES):
                    cur.execute(
                        """
                        INSERT INTO genres (name) VALUES (%s)
                        ON CONFLICT (name) DO NOTHING
                        """,
                        (genre_name,)
                    )
            conn.commit()
    except Exception as exc:
        logger.error("DB Init Error: %s", exc)


def is_recently_posted(tmdb_id: int, media_type: str, title: str = None) -> bool:
    """Check if the movie/show was already posted today. Supports tmdb_id or title lookup."""
    if not os.getenv("DATABASE_URL"):
        return False
        
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                if tmdb_id:
                    cur.execute(
                        """
                        SELECT 1 FROM publications 
                        WHERE tmdb_id = %s AND media_type = %s
                          AND posted_at >= CURRENT_DATE
                        LIMIT 1
                        """,
                        (tmdb_id, media_type)
                    )
                elif title:
                    cur.execute(
                        """
                        SELECT 1 FROM publications 
                        WHERE LOWER(title) = LOWER(%s) AND media_type = %s
                          AND posted_at >= CURRENT_DATE
                        LIMIT 1
                        """,
                        (title, media_type)
                    )
                else:
                    return False
                return cur.fetchone() is not None
    except Exception as exc:
        logger.error("DB Query Error (is_recently_posted): %s", exc)
        return False


def save_publication(
    title: str, 
    media_type: str, 
    tmdb_id: int, 
    score: int, 
    genres: List[str], 
    poster_url: str, 
    year: Optional[int],
    original_title: str = "",
    tmdb_score: float = 0.0,
    positive_comment: str = "",
    negative_comment: str = "",
    rating: int = 0,
    episodes_count: int = 0,
    parts_count: int = 0,
    is_top: bool = False,
    discussion_count: int = 0
) -> Optional[int]:
    """Save a successfully posted publication to the database with genre relations."""
    if not os.getenv("DATABASE_URL"):
        return None

    try:
        with connect() as conn:
            with conn.cursor() as cur:
                # 1. Insert or update publication
                cur.execute(
                    """
                    INSERT INTO publications 
                        (title, original_title, media_type, tmdb_id, score, tmdb_score, 
                         genres, poster_url, year, positive_comment, negative_comment, 
                         rating, episodes_count, parts_count, is_top, discussion_count, posted_at)
                    VALUES 
                        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (tmdb_id, media_type) DO UPDATE 
                    SET posted_at = NOW(), 
                        score = EXCLUDED.score, 
                        genres = EXCLUDED.genres,
                        positive_comment = EXCLUDED.positive_comment,
                        negative_comment = EXCLUDED.negative_comment,
                        rating = EXCLUDED.rating,
                        episodes_count = EXCLUDED.episodes_count,
                        parts_count = EXCLUDED.parts_count,
                        is_top = EXCLUDED.is_top,
                        discussion_count = EXCLUDED.discussion_count
                    RETURNING id
                    """,
                    (title, original_title, media_type, tmdb_id, score, tmdb_score, 
                     genres, poster_url, year, positive_comment, negative_comment, 
                     rating, episodes_count, parts_count, is_top, discussion_count)
                )
                pub_id = cur.fetchone()['id']

                # 2. Insert genres relationships
                if genres:
                    for genre_name in genres:
                        # Ensure genre exists, fetch its id
                        cur.execute(
                            """
                            INSERT INTO genres (name) VALUES (%s)
                            ON CONFLICT (name) DO NOTHING
                            RETURNING id
                            """,
                            (genre_name,)
                        )
                        row = cur.fetchone()
                        if row:
                            genre_id = row['id']
                        else:
                            cur.execute("SELECT id FROM genres WHERE name = %s", (genre_name,))
                            genre_id = cur.fetchone()['id']
                            
                        # Link publication to genre
                        cur.execute(
                            """
                            INSERT INTO publication_genres (publication_id, genre_id) 
                            VALUES (%s, %s)
                            ON CONFLICT DO NOTHING
                            """,
                            (pub_id, genre_id)
                        )
            conn.commit()
            return pub_id
    except Exception as exc:
        logger.error("DB Insert Error (save_publication): %s", exc)
        return None


def get_top_by_genre(genre_name: str, limit: int = 10, period_days: int = 30) -> List[Dict]:
    """Get top scored publications for a specific genre over the last period."""
    if not os.getenv("DATABASE_URL"):
        return []

    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT p.* 
                    FROM publications p
                    JOIN publication_genres pg ON p.id = pg.publication_id
                    JOIN genres g ON pg.genre_id = g.id
                    WHERE g.name = %s
                      AND p.posted_at >= NOW() - INTERVAL '1 day' * %s
                    ORDER BY p.score DESC 
                    LIMIT %s
                    """,
                    (genre_name, period_days, limit)
                )
                return cur.fetchall()
    except Exception as exc:
        logger.error("DB Query Error (get_top_by_genre): %s", exc)
        return []


def get_monthly_top(limit: int = 10) -> List[Dict]:
    """Get the top scored publications posted this month."""
    if not os.getenv("DATABASE_URL"):
        return []

    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * 
                    FROM publications 
                    WHERE posted_at >= date_trunc('month', NOW())
                    ORDER BY score DESC 
                    LIMIT %s
                    """,
                    (limit,)
                )
                return cur.fetchall()
    except Exception as exc:
        logger.error("DB Query Error (get_monthly_top): %s", exc)
        return []


def save_daily_top(movie_ids: List[int], show_ids: List[int]) -> None:
    """Save today's top movies and shows to daily_top table."""
    if not os.getenv("DATABASE_URL"):
        return

    movie1 = movie_ids[0] if len(movie_ids) > 0 else None
    movie2 = movie_ids[1] if len(movie_ids) > 1 else None
    show1 = show_ids[0] if len(show_ids) > 0 else None
    show2 = show_ids[1] if len(show_ids) > 1 else None

    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO daily_top (date, top_movie_1_id, top_movie_2_id, top_show_1_id, top_show_2_id)
                    VALUES (CURRENT_DATE, %s, %s, %s, %s)
                    ON CONFLICT (date) DO UPDATE 
                    SET top_movie_1_id = EXCLUDED.top_movie_1_id,
                        top_movie_2_id = EXCLUDED.top_movie_2_id,
                        top_show_1_id = EXCLUDED.top_show_1_id,
                        top_show_2_id = EXCLUDED.top_show_2_id,
                        created_at = NOW()
                    """,
                    (movie1, movie2, show1, show2)
                )
            conn.commit()
    except Exception as exc:
        logger.error("DB Insert Error (save_daily_top): %s", exc)


def get_today_top() -> Optional[Dict]:
    """Return today's top list joined with publications data."""
    if not os.getenv("DATABASE_URL"):
        return None

    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 
                        dt.date,
                        row_to_json(m1.*) as top_movie_1,
                        row_to_json(m2.*) as top_movie_2,
                        row_to_json(s1.*) as top_show_1,
                        row_to_json(s2.*) as top_show_2
                    FROM daily_top dt
                    LEFT JOIN publications m1 ON dt.top_movie_1_id = m1.id
                    LEFT JOIN publications m2 ON dt.top_movie_2_id = m2.id
                    LEFT JOIN publications s1 ON dt.top_show_1_id = s1.id
                    LEFT JOIN publications s2 ON dt.top_show_2_id = s2.id
                    WHERE dt.date = CURRENT_DATE
                    LIMIT 1
                    """
                )
                return cur.fetchone()
    except Exception as exc:
        logger.error("DB Query Error (get_today_top): %s", exc)
        return None

