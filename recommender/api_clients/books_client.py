"""
recommender/api_clients/books_client.py

Google Books API client for Bingr.
Fetches book recommendations based on titles, genres, and mood.
"""

import os
import requests
from typing import Optional

GOOGLE_BOOKS_API_KEY = os.getenv("GOOGLE_BOOKS_API_KEY", "AIzaSyDTQ4yJLrYhkkSSJX70v6gp3hXO43mSl4I")
GOOGLE_BOOKS_BASE_URL = "https://www.googleapis.com/books/v1/volumes"

GENRE_MAP = {
    "mystery":          "mystery",
    "sci-fi":           "science fiction",
    "fantasy":          "fantasy",
    "romance":          "romance",
    "thriller":         "thriller",
    "horror":           "horror",
    "drama":            "drama",
    "comedy":           "humor",
    "historical":       "historical fiction",
    "adventure":        "adventure",
    "literary fiction": "literary fiction",
    "biography":        "biography",
    "philosophy":       "philosophy",
    "crime":            "crime",
    "psychological":    "psychological fiction",
    "action":           "action",
}

MOOD_KEYWORDS = {
    "dark & intense":    "dark",
    "light & feel-good": "feel-good",
    "mind-bending":      "mind-bending",
    "slow & atmospheric":"atmospheric",
    "fast-paced":        "gripping",
    "emotional":         "emotional",
    "funny & clever":    "funny",
    "underrated":        "underrated",
}


def _build_query(
    favorites: list[str],
    genres: list[str],
    mood: Optional[str],
) -> str:
    parts = []

    for title in favorites[:2]:
        parts.append(f'"{title}"')

    for genre in genres[:2]:
        key = genre.lower()
        subject = GENRE_MAP.get(key, key)
        parts.append(f"subject:{subject}")

    if mood:
        for keyword, hint in MOOD_KEYWORDS.items():
            if keyword in mood.lower():
                parts.append(hint)
                break

    return "+".join(parts) if parts else "bestseller fiction"


def get_book_recommendations(
    favorites: list[str] = [],
    genres: list[str] = [],
    mood: Optional[str] = None,
    max_results: int = 6,
) -> list[dict]:
    """
    Fetch book recommendations from the Google Books API.

    Args:
        favorites:   List of book/movie titles the user likes.
        genres:      List of genre strings (e.g. ["Thriller", "Sci-Fi"]).
        mood:        Optional mood string (e.g. "mind-bending").
        max_results: Number of results to return (max 40 per Google's API).

    Returns:
        List of dicts with keys: title, authors, year, genres,
        description, rating, thumbnail, info_link.
    """
    query = _build_query(favorites, genres, mood)

    params = {
        "q":           query,
        "maxResults":  max_results,
        "printType":   "books",
        "orderBy":     "relevance",
        "langRestrict":"en",
        "key":         GOOGLE_BOOKS_API_KEY,
    }

    response = requests.get(GOOGLE_BOOKS_BASE_URL, params=params, timeout=10)
    response.raise_for_status()

    data = response.json()
    items = data.get("items", [])

    if not items:
        return []

    results = []
    for item in items:
        info = item.get("volumeInfo", {})
        image_links = info.get("imageLinks", {})

        raw_description = info.get("description", "")
        clean_description = (
            raw_description[:300] + "..." if len(raw_description) > 300 else raw_description
        ) or "No description available."

        results.append({
            "title":       info.get("title", "Unknown Title"),
            "authors":     info.get("authors", ["Unknown Author"]),
            "year":        (info.get("publishedDate", "") or "")[:4] or None,
            "genres":      info.get("categories", genres)[:2],
            "description": clean_description,
            "rating":      info.get("averageRating"),
            "rating_count":info.get("ratingsCount"),
            "thumbnail":   image_links.get("thumbnail") or image_links.get("smallThumbnail"),
            "info_link":   info.get("infoLink"),
            "page_count":  info.get("pageCount"),
            "language":    info.get("language"),
        })

    return results


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    books = get_book_recommendations(
        favorites=["Gone Girl", "The Girl with the Dragon Tattoo"],
        genres=["Thriller", "Crime"],
        mood="dark & intense",
        max_results=3,
    )
    for b in books:
        print(f"{b['title']} ({b['year']}) — {', '.join(b['authors'])}")
        print(f"  Rating: {b['rating']} | Pages: {b['page_count']}")
        print(f"  {b['description'][:120]}...")
        print()
