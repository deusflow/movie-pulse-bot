from typing import List, Optional
from pydantic import BaseModel

class ItemResponse(BaseModel):
    id: int
    title: str
    type: str
    rating: Optional[int] = None
    poster_url: Optional[str] = None
    genres: List[str] = []
    positive_comment: Optional[str] = None
    negative_comment: Optional[str] = None
    episodes_count: Optional[int] = None
    parts_count: Optional[int] = None
    year: Optional[int] = None

class HealthResponse(BaseModel):
    status: str
