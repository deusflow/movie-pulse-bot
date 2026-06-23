import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL is not set in the environment")
    
    conn = psycopg2.connect(url, cursor_factory=RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()
