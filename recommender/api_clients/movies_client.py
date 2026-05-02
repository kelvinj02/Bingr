import os
import requests
from typing import Optional
from recommender import cache

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

GENRE_MAP = {
    "mystery":          9648,    # Mystery
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


@cache.memoize(timeout=86400)
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


@cache.memoize(timeout=3600)
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


@cache.memoize(timeout=3600)
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
        "id": str(item.get("id")),
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
    favorites: list[str] = None,
    genres: list[str] = None,
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
    favorites = favorites or []
    genres = genres or []
    results = []
    seen_ids = set()

    # find movies similar to the user's favorites
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

    # fill remaining slots via genre discovery
    if len(results) < max_results and genres:
        genre_ids = _get_genre_ids(genres)
        if genre_ids:
            discovered = _discover_movies(genre_ids, max_results)
            for item in discovered:
                if item["id"] not in seen_ids and len(results) < max_results:
                    seen_ids.add(item["id"])
                    results.append(_format_movie(item, genres, mood))

    # fall back to popular movies
    if not results:
        try:
            url = f"{TMDB_BASE_URL}/movie/popular"
            params = {"api_key": TMDB_API_KEY, "page": 1, "language": "en-US"}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            for item in response.json().get("results", [])[:max_results]:
                results.append(_format_movie(item, genres, mood))
        except Exception:
            return []

    return results

def get_movie(movie_id: str) -> Optional[dict]:
    url=f"{TMDB_BASE_URL}/movie/{movie_id}"
    params={"api_key": TMDB_API_KEY, "language": "en-US"}
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        item=response.json()
        return _format_movie(item, [], None)
    except Exception:
        return None

@cache.memoize(timeout=600)
def get_trending_movies(max_results: int = 5) -> list[dict]:
    url = f"{TMDB_BASE_URL}/trending/movie/week"
    params = {"api_key": TMDB_API_KEY, "language": "en-US"}
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        results = response.json().get("results", [])[:max_results]
        movies = [_format_movie(item, [], None) for item in results]
        for m in movies:
            m['poster_url'] = m.pop('thumbnail', None)
        return movies
    except Exception:
        return []

def search_movie_by_title(title: str) -> Optional[int]:
    """Public wrapper: return TMDB movie ID for a given title."""
    return _search_movie_id(title)


def _get_certification(movie_id: int) -> Optional[str]:
    """Fetch the US certification (PG, R, etc.) from TMDB release_dates."""
    try:
        r = requests.get(
            f"{TMDB_BASE_URL}/movie/{movie_id}/release_dates",
            params={"api_key": TMDB_API_KEY},
            timeout=10,
        )
        r.raise_for_status()
        for country in r.json().get("results", []):
            if country.get("iso_3166_1") == "US":
                for release in country.get("release_dates", []):
                    cert = release.get("certification", "").strip()
                    if cert:
                        return cert
    except Exception:
        pass
    return None


@cache.memoize(timeout=3600)
def get_movie_full(movie_id: int) -> Optional[dict]:
    """Fetch full movie detail + cast/crew + certification from TMDB."""
    params = {"api_key": TMDB_API_KEY, "language": "en-US"}
    try:
        d = requests.get(f"{TMDB_BASE_URL}/movie/{movie_id}", params=params, timeout=10)
        d.raise_for_status()
        c = requests.get(f"{TMDB_BASE_URL}/movie/{movie_id}/credits", params=params, timeout=10)
        c.raise_for_status()
        item    = d.json()
        credits = c.json()

        crew      = credits.get("crew", [])
        directors = [p["name"] for p in crew if p["job"] == "Director"]
        producers = [p["name"] for p in crew
                     if p["job"] in ("Producer", "Executive Producer")][:3]
        cast      = [{"name": a["name"], "character": a.get("character", "")}
                     for a in credits.get("cast", [])[:10]]

        poster = item.get("poster_path")
        return {
            "id":            str(item.get("id")),
            "title":         item.get("title", "Unknown"),
            "tagline":       item.get("tagline") or "",
            "overview":      item.get("overview") or "",
            "release_date":  (item.get("release_date") or "")[:4],
            "runtime":       item.get("runtime"),
            "genres":        [g["name"] for g in item.get("genres", [])],
            "rating":        item.get("vote_average"),
            "rating_count":  item.get("vote_count"),
            "poster_url":    f"{TMDB_IMAGE_BASE}{poster}" if poster else None,
            "directors":     directors,
            "producers":     producers,
            "cast":          cast,
            "info_link":     f"https://www.themoviedb.org/movie/{item.get('id')}",
            "certification": _get_certification(movie_id),
        }
    except Exception:
        return None


@cache.memoize(timeout=900)
def search_movies(query: str, max_results: int = 15) -> list[dict]:
    """Search TMDB by title keyword, returns movies with poster_url included."""
    url = f"{TMDB_BASE_URL}/search/movie"
    params = {"api_key": TMDB_API_KEY, "query": query, "page": 1, "language": "en-US"}
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        results = response.json().get("results", [])[:max_results]
        movies = [_format_movie(item, [], None) for item in results]
        for m in movies:
            m['poster_url'] = m.pop('thumbnail', None)
        return movies
    except Exception:
        return []


def get_movie_poster(movie_id: int) -> Optional[str]:
    url = f"{TMDB_BASE_URL}/movie/{movie_id}"
    params = {"api_key": TMDB_API_KEY, "language": "en-US"}
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        poster = response.json().get("poster_path")
        return f"{TMDB_IMAGE_BASE}{poster}" if poster else None
    except Exception:
        return None
