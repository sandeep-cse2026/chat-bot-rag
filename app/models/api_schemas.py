"""Pydantic models for external API response validation.

These models normalize and validate data from Jikan, TV Maze, and Open Library
APIs into a consistent internal representation. They are used by the API clients
to parse raw JSON into typed, validated objects.
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional


# ══════════════════════════════════════════════════════════════════════
# Jikan API (Anime / Manga) Models
# ══════════════════════════════════════════════════════════════════════

class AnimeData(BaseModel):
    """Normalized anime data from Jikan API."""
    mal_id: int
    title: str
    title_english: Optional[str] = None
    title_japanese: Optional[str] = None
    synopsis: Optional[str] = None
    score: Optional[float] = None
    scored_by: Optional[int] = None
    rank: Optional[int] = None
    popularity: Optional[int] = None
    episodes: Optional[int] = None
    status: Optional[str] = None
    rating: Optional[str] = None
    source: Optional[str] = None
    duration: Optional[str] = None
    season: Optional[str] = None
    year: Optional[int] = None
    genres: list[str] = Field(default_factory=list)
    studios: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    url: Optional[str] = None
    image_url: Optional[str] = None
    trailer_url: Optional[str] = None


class MangaData(BaseModel):
    """Normalized manga data from Jikan API."""
    mal_id: int
    title: str
    title_english: Optional[str] = None
    title_japanese: Optional[str] = None
    synopsis: Optional[str] = None
    score: Optional[float] = None
    scored_by: Optional[int] = None
    rank: Optional[int] = None
    popularity: Optional[int] = None
    chapters: Optional[int] = None
    volumes: Optional[int] = None
    status: Optional[str] = None
    type: Optional[str] = None
    genres: list[str] = Field(default_factory=list)
    authors: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    url: Optional[str] = None
    image_url: Optional[str] = None


class AnimeCharacter(BaseModel):
    """Character data from Jikan anime characters endpoint."""
    name: str
    role: Optional[str] = None
    image_url: Optional[str] = None


class AnimeRecommendation(BaseModel):
    """Recommendation data from Jikan anime recommendations endpoint."""
    mal_id: int
    title: str
    url: Optional[str] = None
    image_url: Optional[str] = None
    votes: int = 0


# ══════════════════════════════════════════════════════════════════════
# TV Maze API Models
# ══════════════════════════════════════════════════════════════════════

class TVShowData(BaseModel):
    """Normalized TV show data from TV Maze API."""
    id: int
    name: str
    summary: Optional[str] = None       # Already HTML-stripped
    genres: list[str] = Field(default_factory=list)
    status: Optional[str] = None
    premiered: Optional[str] = None
    ended: Optional[str] = None
    rating: Optional[float] = None
    network: Optional[str] = None
    schedule_time: Optional[str] = None
    schedule_days: list[str] = Field(default_factory=list)
    runtime: Optional[int] = None
    language: Optional[str] = None
    type: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = None


class TVEpisodeData(BaseModel):
    """Normalized TV episode data from TV Maze API."""
    id: int
    name: str
    season: int
    number: Optional[int] = None
    airdate: Optional[str] = None
    runtime: Optional[int] = None
    summary: Optional[str] = None       # Already HTML-stripped
    url: Optional[str] = None


class TVCastMember(BaseModel):
    """Cast member data from TV Maze API."""
    person_name: str
    character_name: Optional[str] = None
    person_image_url: Optional[str] = None


class TVScheduleEntry(BaseModel):
    """Schedule entry from TV Maze API."""
    show_name: str
    episode_name: Optional[str] = None
    season: Optional[int] = None
    number: Optional[int] = None
    airtime: Optional[str] = None
    network: Optional[str] = None


class TVPersonData(BaseModel):
    """Person (actor/crew) data from TV Maze API."""
    id: int
    name: str
    birthday: Optional[str] = None
    country: Optional[str] = None
    image_url: Optional[str] = None
    url: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════
# Open Library API Models
# ══════════════════════════════════════════════════════════════════════

class BookData(BaseModel):
    """Normalized book data from Open Library search API."""
    title: str
    author_name: list[str] = Field(default_factory=list)
    first_publish_year: Optional[int] = None
    edition_count: Optional[int] = None
    isbn: list[str] = Field(default_factory=list)
    subject: list[str] = Field(default_factory=list)
    cover_id: Optional[int] = None
    key: Optional[str] = None           # Open Library work key
    ratings_average: Optional[float] = None
    number_of_pages: Optional[int] = None
    language: list[str] = Field(default_factory=list)
    publisher: list[str] = Field(default_factory=list)
    cover_url: Optional[str] = None


class BookWorkData(BaseModel):
    """Work details from Open Library works API."""
    title: str
    key: str
    description: Optional[str] = None
    subjects: list[str] = Field(default_factory=list)
    covers: list[int] = Field(default_factory=list)
    first_publish_date: Optional[str] = None


class BookEditionData(BaseModel):
    """Edition data from Open Library ISBN lookup."""
    title: str
    isbn_13: list[str] = Field(default_factory=list)
    isbn_10: list[str] = Field(default_factory=list)
    publishers: list[str] = Field(default_factory=list)
    publish_date: Optional[str] = None
    number_of_pages: Optional[int] = None
    covers: list[int] = Field(default_factory=list)
    key: Optional[str] = None
    cover_url: Optional[str] = None


class AuthorData(BaseModel):
    """Author data from Open Library authors API."""
    name: str
    key: str
    birth_date: Optional[str] = None
    death_date: Optional[str] = None
    bio: Optional[str] = None
    photo_url: Optional[str] = None
    top_work: Optional[str] = None
    work_count: Optional[int] = None
