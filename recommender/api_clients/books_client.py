import os
import re
import urllib.parse
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    """Clean a Google Books thumbnail URL: remove curl effect, upgrade to https."""
    if not url:
        return url
    url = url.replace('&edge=curl', '').replace('http://', 'https://')
    return url


@cache.memoize(timeout=900)
def _get_openlibrary_cover(title: str) -> Optional[str]:
    """Search Open Library for a large cover image by title."""
    try:
        resp = requests.get(
            "https://openlibrary.org/search.json",
            params={"title": title, "fields": "cover_i,isbn", "limit": 5},
            timeout=8,
        )
        docs = resp.json().get("docs", [])
        # Prefer cover_id (most reliable) — check all results
        for doc in docs:
            cover_id = doc.get("cover_i")
            if cover_id:
                return f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
        # Fall back to ISBN from any result
        for doc in docs:
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


def get_book_recommendations(
    favorites: list[str] = None,
    genres: list[str] = None,
    mood: Optional[str] = None,
    max_results: int = 20,
) -> list[dict]:
    favorites = list(favorites or [])
    genres    = list(genres    or [])
    _key = f"book_recs_{max_results}_{repr(sorted(favorites))}_{repr(sorted(genres))}_{mood}"
    cached = cache.get(_key)
    if cached is not None:
        return cached

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

    # Pass 1 — deduplicate and extract Google Books thumbnails
    candidates, seen_titles = [], set()
    for item in items:
        info       = item.get("volumeInfo", {})
        book_title = info.get("title", "Unknown Title")
        if book_title in seen_titles:
            continue
        seen_titles.add(book_title)
        links     = info.get("imageLinks", {})
        thumbnail = _upgrade_cover_url(links.get("thumbnail") or links.get("smallThumbnail"))
        candidates.append({"id": item.get("id"), "title": book_title,
                           "thumbnail": thumbnail, "info": info})

    # Pass 2 — fetch Open Library covers in parallel for books that still need one
    need_ol = [c for c in candidates if not c["thumbnail"]]
    if need_ol:
        with ThreadPoolExecutor(max_workers=min(8, len(need_ol))) as ex:
            futures = {ex.submit(_get_openlibrary_cover, c["title"]): c for c in need_ol}
            for f in as_completed(futures):
                futures[f]["thumbnail"] = f.result()

    # Pass 3 — build final list, skip anything still without a cover
    results = []
    for c in candidates:
        if not c["thumbnail"]:
            continue
        info = c["info"]
        raw  = info.get("description", "")
        results.append({
            "id":          c["id"],
            "title":       c["title"],
            "authors":     info.get("authors", ["Unknown Author"]),
            "year":        (info.get("publishedDate", "") or "")[:4] or None,
            "genres":      info.get("categories", genres)[:2],
            "description": (raw[:300] + "..." if len(raw) > 300 else raw) or "No description available.",
            "rating":      info.get("averageRating"),
            "rating_count":info.get("ratingsCount"),
            "thumbnail":   c["thumbnail"],
            "info_link":   info.get("infoLink"),
            "page_count":  info.get("pageCount"),
            "language":    info.get("language"),
        })
    if results:
        cache.set(_key, results, timeout=900)
    return results


@cache.memoize(timeout=900)
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
        book_title = info.get("title", "Unknown Title")
        return {
            "id":          item.get("id"),
            "title":       book_title,
            "authors":     info.get("authors", ["Unknown Author"]),
            "year":        (info.get("publishedDate", "") or "")[:4] or None,
            "genres":      info.get("categories", [])[:2],
            "description": clean_description,
            "rating":      info.get("averageRating"),
            "rating_count":info.get("ratingsCount"),
            "thumbnail":   _upgrade_cover_url(
                               image_links.get("thumbnail") or image_links.get("smallThumbnail")
                           ) or _get_openlibrary_cover(book_title),
            "info_link":   info.get("infoLink"),
            "page_count":  info.get("pageCount"),
            "language":    info.get("language"),
        }
    except Exception:
        return None

@cache.memoize(timeout=900)
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


@cache.memoize(timeout=900)
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


@cache.memoize(timeout=900)
def get_book_cover(title: str) -> str:
    # Strip series info "(Series, #N)" and subtitle after ":" or "—"
    clean = re.sub(r'\s*[\(\[].*?[\)\]]', '', title).strip()
    clean = re.split(r'[:—]', clean)[0].strip() or title
    queries = [f'intitle:"{title}"', f'intitle:"{clean}"', clean]
    seen = set()
    for query in queries:
        if query in seen:
            continue
        seen.add(query)
        params = {"q": query, "maxResults": 3, "key": GOOGLE_BOOKS_API_KEY}
        try:
            response = requests.get(GOOGLE_BOOKS_BASE_URL, params=params, timeout=10)
            for item in response.json().get("items", []):
                links = item.get("volumeInfo", {}).get("imageLinks", {})
                url = links.get("thumbnail") or links.get("smallThumbnail")
                upgraded = _upgrade_cover_url(url)
                if upgraded:
                    return upgraded
        except Exception:
            pass
    return _get_openlibrary_cover(clean)


_TRENDING_GENRE_QUERIES = [
    "subject:fiction",
    "subject:mystery thriller",
    "subject:romance",
    "subject:science fiction fantasy",
    "subject:biography memoir",
    "subject:history",
    "subject:horror",
    "subject:self-help",
    "subject:crime",
    "subject:adventure",
]


def get_trending_books(max_results: int = 20) -> list[dict]:
    _key = f"trending_books_{max_results}"
    cached = cache.get(_key)
    if cached is not None:
        return cached

    import random as _random
    from datetime import datetime

    cutoff_yr = str(datetime.now().year)
    per_query = max(8, (max_results * 4) // len(_TRENDING_GENRE_QUERIES))

    def _pub_sort_key(pub: str) -> str:
        if not pub:
            return "0000"
        return pub[:7] if len(pub) >= 7 else pub

    def _fetch(query: str) -> list:
        params = {
            "q":           query,
            "orderBy":     "newest",
            "maxResults":  per_query,
            "printType":   "books",
            "langRestrict":"en",
            "key":         GOOGLE_BOOKS_API_KEY,
        }
        try:
            resp = requests.get(GOOGLE_BOOKS_BASE_URL, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json().get("items", [])
        except Exception:
            return []

    pool, seen = [], set()
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(_fetch, q) for q in _TRENDING_GENRE_QUERIES]
        for future in as_completed(futures):
            for item in future.result():
                info  = item.get("volumeInfo", {})
                title = info.get("title", "").strip()
                if not title or title in seen:
                    continue
                links = info.get("imageLinks", {})
                thumbnail = _upgrade_cover_url(
                    links.get("thumbnail") or links.get("smallThumbnail")
                )
                if not thumbnail:
                    continue
                seen.add(title)
                pub = (info.get("publishedDate", "") or "").strip()
                pool.append({
                    "id":          item.get("id"),
                    "title":       title,
                    "authors":     info.get("authors", ["Unknown Author"]),
                    "year":        pub[:4] or None,
                    "genres":      info.get("categories", [])[:2],
                    "description": (info.get("description", "") or "")[:300],
                    "rating":      info.get("averageRating"),
                    "rating_count":info.get("ratingsCount"),
                    "thumbnail":   thumbnail,
                    "info_link":   info.get("infoLink"),
                    "_pub_key":    _pub_sort_key(pub),
                })

    pool.sort(key=lambda b: b.pop("_pub_key"), reverse=True)
    recent = [b for b in pool if (b.get("year") or "0") >= cutoff_yr]
    older  = [b for b in pool if b not in recent]
    _random.shuffle(recent)
    _random.shuffle(older)
    result = (recent + older)[:max_results]
    if result:
        cache.set(_key, result, timeout=900)
    return result
