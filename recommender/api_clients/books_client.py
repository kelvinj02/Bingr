import os
import re
import requests
from typing import Optional
from recommender import cache

GOOGLE_BOOKS_API_KEY = os.getenv("BOOKS_API_KEY")
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


def _upgrade_cover_url(url: Optional[str]) -> Optional[str]:
    """Replace zoom=N with zoom=0 in a Google Books URL to get the full-size cover."""
    if not url:
        return url
    url = re.sub(r'zoom=\d+', 'zoom=0', url)
    url = url.replace('&edge=curl', '')
    return url


def _get_openlibrary_cover(title: str) -> Optional[str]:
    """Search Open Library for a large cover image by title."""
    try:
        resp = requests.get(
            "https://openlibrary.org/search.json",
            params={"title": title, "fields": "cover_i,isbn", "limit": 1},
            timeout=8,
        )
        docs = resp.json().get("docs", [])
        if not docs:
            return None
        doc = docs[0]
        cover_id = doc.get("cover_i")
        if cover_id:
            return f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
        isbns = doc.get("isbn", [])
        if isbns:
            return f"https://covers.openlibrary.org/b/isbn/{isbns[0]}-L.jpg"
    except Exception:
        pass
    return None


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


@cache.memoize(timeout=600)
def get_book_recommendations(
    favorites: list[str] = None,
    genres: list[str] = None,
    mood: Optional[str] = None,
    max_results: int = 20,
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
    favorites= favorites or []
    genres=genres or []
    query = _build_query(favorites, genres, mood)

    params = {
        "q":           query,
        "maxResults":  max_results,
        "printType":   "books",
        "orderBy":     "relevance",
        "langRestrict":"en",
        "key":         GOOGLE_BOOKS_API_KEY,
    }
    
    #(fixed) error handling (try, except)
    try:
        response = requests.get(GOOGLE_BOOKS_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception:
        return []

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
            "id":   item.get("id"),
            "title":       info.get("title", "Unknown Title"),
            "authors":     info.get("authors", ["Unknown Author"]),
            "year":        (info.get("publishedDate", "") or "")[:4] or None,
            "genres":      info.get("categories", genres)[:2],
            "description": clean_description,
            "rating":      info.get("averageRating"),
            "rating_count":info.get("ratingsCount"),
            "thumbnail":   _upgrade_cover_url(
                               image_links.get("thumbnail") or image_links.get("smallThumbnail")),
            "info_link":   info.get("infoLink"),
            "page_count":  info.get("pageCount"),
            "language":    info.get("language"),
        })

    return results


def get_book(book_id: str) -> Optional[dict]:
    url = f"{GOOGLE_BOOKS_BASE_URL}/{book_id}"
    params = {"key": GOOGLE_BOOKS_API_KEY}
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        item = response.json()
        info = item.get("volumeInfo", {})
        image_links = info.get("imageLinks", {})
        raw_description = info.get("description", "")
        clean_description = (
            raw_description[:300] + "..." if len(raw_description) > 300 else raw_description
        ) or "No description available."
        return {
            "id":          item.get("id"),
            "title":       info.get("title", "Unknown Title"),
            "authors":     info.get("authors", ["Unknown Author"]),
            "year":        (info.get("publishedDate", "") or "")[:4] or None,
            "genres":      info.get("categories", [])[:2],
            "description": clean_description,
            "rating":      info.get("averageRating"),
            "rating_count":info.get("ratingsCount"),
            "thumbnail":   _upgrade_cover_url(
                               image_links.get("thumbnail") or image_links.get("smallThumbnail")),
            "info_link":   info.get("infoLink"),
            "page_count":  info.get("pageCount"),
            "language":    info.get("language"),
        }
    except Exception:
        return None

@cache.memoize(timeout=86400)
def get_book_characters(title: str) -> list[str]:
    """Return character names for a book via Open Library subject_people field."""
    try:
        resp = requests.get(
            "https://openlibrary.org/search.json",
            params={"title": title, "fields": "title,subject_people", "limit": 1},
            timeout=10,
        )
        resp.raise_for_status()
        docs = resp.json().get("docs", [])
        if docs:
            return docs[0].get("subject_people", [])[:10]
        return []
    except Exception:
        return []


@cache.memoize(timeout=86400)
def get_book_by_title(title: str) -> Optional[dict]:
    """Search Google Books by title and return a book dict keyed like the ML dataframe."""
    # Try exact intitle search first, then a plain keyword search as fallback
    queries = [f'intitle:"{title}"', f'intitle:{title}', title]
    for query in queries:
        params = {
            "q":          query,
            "maxResults": 1,
            "printType":  "books",
            "key":        GOOGLE_BOOKS_API_KEY,
        }
        try:
            response = requests.get(GOOGLE_BOOKS_BASE_URL, params=params, timeout=10)
            items = response.json().get("items", [])
            if not items:
                continue
            info        = items[0].get("volumeInfo", {})
            image_links = info.get("imageLinks", {})
            raw_desc    = info.get("description", "")
            description = (raw_desc[:400] + "…" if len(raw_desc) > 400 else raw_desc) or ""
            authors     = info.get("authors", ["Unknown Author"])
            return {
                "Book":         info.get("title", title),
                "Author":       ", ".join(authors) if isinstance(authors, list) else authors,
                "Avg_Rating":   info.get("averageRating"),
                "Num_Ratings":  info.get("ratingsCount"),
                "Description":  description,
                "Genres_Clean": ", ".join(info.get("categories", [])[:3]),
                "URL":          info.get("infoLink", ""),
                "_cover_url":   _upgrade_cover_url(
                                    image_links.get("thumbnail") or image_links.get("smallThumbnail"))
                                or _get_openlibrary_cover(title),
            }
        except Exception:
            continue
    return None


@cache.memoize(timeout=86400)
def get_book_cover(title: str) -> Optional[str]:
    params = {"q": f'intitle:"{title}"', "maxResults": 1, "key": GOOGLE_BOOKS_API_KEY}
    try:
        response = requests.get(GOOGLE_BOOKS_BASE_URL, params=params, timeout=10)
        items = response.json().get("items", [])
        if items:
            links = items[0].get("volumeInfo", {}).get("imageLinks", {})
            url = links.get("thumbnail") or links.get("smallThumbnail")
            upgraded = _upgrade_cover_url(url)
            if upgraded:
                return upgraded
    except Exception:
        pass
    return _get_openlibrary_cover(title)
