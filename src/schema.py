"""
Stage 4 — the schema.

This is the "recipe" every raw record is checked against before it is
allowed into books.json. Anything that fails validation goes to
errors.json instead, with the reason.
"""

from typing import Optional

from pydantic import BaseModel, HttpUrl, field_validator


class RawBookRecord(BaseModel):
    """What we scrape straight off the page, before any cleaning."""

    title: str
    product_url: str
    price_text: str
    availability_text: str
    rating_text: str
    description: Optional[str] = None
    source_page: str
    fetched_at: str


class BookRecord(BaseModel):
    """The clean, validated record that actually gets stored."""

    title: str
    product_url: HttpUrl
    price_text: str
    price_gbp: float
    availability_text: str
    rating_text: str
    description: Optional[str] = None
    source_page: str
    fetched_at: str

    @field_validator("price_gbp")
    @classmethod
    def price_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("price_gbp must be a positive number")
        return v

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must not be empty")
        return v
