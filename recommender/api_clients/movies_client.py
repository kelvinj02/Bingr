"""
recommender/api_clients/movies_client.py

TMDB (The Movie Database) API client for Bingr.
Fetches movie recommendations based on titles, genres, and mood.
"""

import os
import requests
from typing import Optional

TMDB_API_KEY = os.getenv("TMDB_API_KEY", "d3b196cc67178a0775343389b1ff3d4b")
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

GENRE_MAP = {
    "mystery":          18,    # Drama (closest match)
    "sci-fi":           878,
    "fantasy":          14,
    "romance":          10749,
    "thriller":         53,
    "horror":           27,
    "drama":            18,
    "comedy":           35,
    "historical":       36,    # History
    "adventure":        12,
    "literary fiction": 18,
    "biography":        99,    # Documentary
    "philosophy":       99,
    "crime":            80,
    "psychological":    53,    # Thriller
    "action":           28,
}

MOOD_KEYWORDS = {
    "dark & intense":    "dark",
    "light & feel-good": "feel-good",
    "mind-bending":      "mind-bending",
    "slow & atmospheric":"atmospheric",
    "fast-paced":        "action",
    "emotional":         "emotional",
    "funny & clever":    "comedy",
    "underrated":        "hidden gem",
}


def _get_genre_ids(genres: list[str]) -> list[int]:
    ids = []
    for genre in genres:
        key = genre.lower()
        genre_id = GENRE_MAP.get(key)
        if genre_id and genre_id not in ids:
            ids.append(genre_id)
    return ids


def _search_movie_id(title: str) -> Optional[int]:
    """Look up a movie's TMDB ID by title, used to find similar movies."""
    url = f"{TMDB_BASE_URL}/search/movie"
    params = {
        "api_key": TMDB_API_KEY,
        "query":   title,
        "page":    1,
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        results = response.json().get("results", [])
        return results[0]["id"] if results else None
    except Exception:
        return None


def _get_similar_movies(movie_id: int, max_results: int) -> list[dict]:
    """Fetch movies similar to a given TMDB movie ID."""
    url = f"{TMDB_BASE_URL}/movie/{movie_id}/similar"
    params = {"api_key": TMDB_API_KEY, "page": 1}
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json().get("results", [])[:max_results]
    except Exception:
        return []


def _discover_movies(genre_ids: list[int], max_results: int) -> list[dict]:
    """Discover movies by genre using TMDB's discover endpoint."""
    url = f"{TMDB_BASE_URL}/discover/movie"
    params = {
        "api_key":              TMDB_API_KEY,
        "with_genres":          ",".join(str(g) for g in genre_ids),
        "sort_by":              "vote_average.desc",
        "vote_count.gte":       20,
        "page":                 1,
        "language":             "en-US",
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json().get("results", [])[:max_results]
    except Exception:
        return []


def _format_movie(item: dict, genres: list[str], mood: Optional[str]) -> dict:
    year = (item.get("release_date", "") or "")[:4] or None
    genre_names = genres[:2] if genres else ["Film"]
    poster = item.get("poster_path")

    return {
        "title":       item.get("title", "Unknown Title"),
        "year":        year,
        "genres":      genre_names,
        "description": item.get("overview", "No description available.")[:300],
        "rating":      item.get("vote_average"),
        "rating_count":item.get("vote_count"),
        "thumbnail":   f"{TMDB_IMAGE_BASE}{poster}" if poster else None,
        "info_link":   f"https://www.themoviedb.org/movie/{item.get('id')}",
        "language":    item.get("original_language"),
        "popularity":  item.get("popularity"),
    }


def get_movie_recommendations(
    favorites: list[str] = [],
    genres: list[str] = [],
    mood: Optional[str] = None,
    max_results: int = 20,
) -> list[dict]:
    """
    Fetch movie recommendations from the TMDB API.

    Args:
        favorites:   List of movie/book titles the user likes.
        genres:      List of genre strings (e.g. ["Thriller", "Sci-Fi"]).
        mood:        Optional mood string (e.g. "dark & intense").
        max_results: Number of results to return.

    Returns:
        List of dicts with keys: title, year, genres, description,
        rating, rating_count, thumbnail, info_link, language, popularity.
    """
    results = []
    seen_ids = set()

    # Strategy 1: find movies similar to the user's favorites
    for title in favorites[:2]:
        if len(results) >= max_results:
            break
        movie_id = _search_movie_id(title)
        if not movie_id:
            continue
        similar = _get_similar_movies(movie_id, max_results)
        for item in similar:
            if item["id"] not in seen_ids and len(results) < max_results:
                seen_ids.add(item["id"])
                results.append(_format_movie(item, genres, mood))

    # Strategy 2: fill remaining slots via genre discovery
    if len(results) < max_results and genres:
        genre_ids = _get_genre_ids(genres)
        if genre_ids:
            discovered = _discover_movies(genre_ids, max_results)
            for item in discovered:
                if item["id"] not in seen_ids and len(results) < max_results:
                    seen_ids.add(item["id"])
                    results.append(_format_movie(item, genres, mood))

    # Strategy 3: fallback to popular movies
    if not results:
        url = f"{TMDB_BASE_URL}/movie/popular"
        params = {"api_key": TMDB_API_KEY, "page": 1, "language": "en-US"}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        for item in response.json().get("results", [])[:max_results]:
            results.append(_format_movie(item, genres, mood))

    return results
