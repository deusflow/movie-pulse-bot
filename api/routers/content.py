import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Security, Query
from fastapi.security.api_key import APIKeyHeader

from api.database import get_db
from api.models import ItemResponse, HealthResponse

router = APIRouter()

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def get_api_key(api_key_header: str = Security(api_key_header)):
    expected_key = os.getenv("API_KEY")
    if not expected_key or not api_key_header or api_key_header != expected_key:
        raise HTTPException(status_code=403, detail="Could not validate API key")
    return api_key_header

def map_item(row: dict) -> dict:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "title": row.get("title"),
        "type": row.get("media_type"),
        "rating": row.get("rating"),
        "poster_url": row.get("poster_url"),
        "genres": row.get("genres", []),
        "positive_comment": row.get("positive_comment"),
        "negative_comment": row.get("negative_comment"),
        "episodes_count": row.get("episodes_count"),
        "parts_count": row.get("parts_count"),
        "year": row.get("year"),
    }

@router.get("/health", response_model=HealthResponse)
def health_check():
    return {"status": "ok"}

@router.get("/api/v1/today")
def get_today_top(conn = Depends(get_db), api_key: str = Depends(get_api_key)):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 
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
        row = cur.fetchone()
        if not row:
            return {"movies": [], "shows": []}
            
        movies = []
        shows = []
        if row.get("top_movie_1"): movies.append(map_item(row["top_movie_1"]))
        if row.get("top_movie_2"): movies.append(map_item(row["top_movie_2"]))
        if row.get("top_show_1"): shows.append(map_item(row["top_show_1"]))
        if row.get("top_show_2"): shows.append(map_item(row["top_show_2"]))
        
        return {"movies": movies, "shows": shows}

@router.get("/api/v1/movies", response_model=List[ItemResponse])
def get_movies(
    genre: Optional[str] = None, 
    limit: int = Query(10, le=50),
    conn = Depends(get_db), 
    api_key: str = Depends(get_api_key)
):
    with conn.cursor() as cur:
        if genre:
            cur.execute(
                """
                SELECT * FROM publications 
                WHERE media_type = 'movie' AND %s = ANY(genres)
                ORDER BY posted_at DESC LIMIT %s
                """,
                (genre, limit)
            )
        else:
            cur.execute(
                """
                SELECT * FROM publications 
                WHERE media_type = 'movie'
                ORDER BY posted_at DESC LIMIT %s
                """,
                (limit,)
            )
        rows = cur.fetchall()
        return [map_item(r) for r in rows]

@router.get("/api/v1/shows", response_model=List[ItemResponse])
def get_shows(
    genre: Optional[str] = None, 
    limit: int = Query(10, le=50),
    conn = Depends(get_db), 
    api_key: str = Depends(get_api_key)
):
    with conn.cursor() as cur:
        if genre:
            cur.execute(
                """
                SELECT * FROM publications 
                WHERE media_type = 'tv' AND %s = ANY(genres)
                ORDER BY posted_at DESC LIMIT %s
                """,
                (genre, limit)
            )
        else:
            cur.execute(
                """
                SELECT * FROM publications 
                WHERE media_type = 'tv'
                ORDER BY posted_at DESC LIMIT %s
                """,
                (limit,)
            )
        rows = cur.fetchall()
        return [map_item(r) for r in rows]

@router.get("/api/v1/item/{tmdb_id}", response_model=ItemResponse)
def get_item(
    tmdb_id: int,
    conn = Depends(get_db),
    api_key: str = Depends(get_api_key)
):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM publications WHERE tmdb_id = %s ORDER BY posted_at DESC LIMIT 1",
            (tmdb_id,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Item not found")
        return map_item(row)
