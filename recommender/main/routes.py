import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import render_template, Blueprint, request, url_for, current_app, copy_current_request_context
from flask_login import current_user
from recommender import db
from recommender.models import UserBook, UserMovie, UserPreference, WishListItem, SearchHistory
from recommender.api_clients.movies_client import get_trending_movies, get_movie_recommendations, search_movies
from recommender.api_clients.books_client import get_book_recommendations, get_trending_books

main = Blueprint('main', __name__)


def _norm_movie(m):
    """Ensure movie dict always has poster_url (rename thumbnail if needed)."""
    if 'poster_url' not in m:
        m['poster_url'] = m.pop('thumbnail', None)
    return m


def _norm_book(b):
    """Ensure book dict always has rating key (map avg_rating if needed)."""
    if 'rating' not in b:
        b['rating'] = b.get('avg_rating')
    return b


def _cached_personalized_movie_items(user_id, top_n):
    """Cache the fully assembled personalized movie list per user for 5 minutes."""
    from recommender import cache as _cache
    _key = f"pers_movies_{user_id}_{top_n}"
    hit = _cache.get(_key)
    if hit is not None:
        return hit
    result = _personalized_movie_items(top_n=top_n)
    _cache.set(_key, result, timeout=300)
    return result


def _cached_personalized_book_items(user_id, top_n):
    """Cache the fully assembled personalized book list per user for 5 minutes."""
    from recommender import cache as _cache
    _key = f"pers_books_{user_id}_{top_n}"
    hit = _cache.get(_key)
    if hit is not None:
        return hit
    result = _personalized_book_items(top_n=top_n)
    _cache.set(_key, result, timeout=300)
    return result


@main.route("/")
@main.route("/home")
def home():
    ccrc = copy_current_request_context
    uid  = current_user.id if current_user.is_authenticated else None
    with ThreadPoolExecutor(max_workers=4) as ex:
        f_trending_movies = ex.submit(get_trending_movies, 10)
        f_trending_books  = ex.submit(get_trending_books, 10)
        if uid:
            f_rec_movies = ex.submit(ccrc(lambda: _cached_personalized_movie_items(uid, 5)))
            f_rec_books  = ex.submit(ccrc(lambda: _cached_personalized_book_items(uid, 5)))

    trend_movies_raw = f_trending_movies.result()
    trend_books_raw  = [_norm_book(b) for b in f_trending_books.result()]

    if not uid:
        rec_movies_raw = trend_movies_raw[:5]
        rec_books_raw  = trend_books_raw[:5] or _csv_fallback_books(5)
    else:
        rec_movies_raw = f_rec_movies.result()
        rec_books_raw  = f_rec_books.result()

    if not trend_books_raw:
        trend_books_raw = rec_books_raw
    if not rec_books_raw:
        rec_books_raw = trend_books_raw[:5]

    rec_items = ([{"kind": "movie", **m} for m in rec_movies_raw] +
                 [{"kind": "book",  **b} for b in rec_books_raw])
    random.shuffle(rec_items)

    rec_book_titles = {i["title"] for i in rec_items if i["kind"] == "book"}
    trend_books_deduped = [b for b in trend_books_raw if b["title"] not in rec_book_titles]
    trend_items = ([{"kind": "movie", **_norm_movie(m)} for m in trend_movies_raw] +
                   [{"kind": "book",  **b} for b in trend_books_deduped])
    random.shuffle(trend_items)
    trend_items = trend_items[:10]

    return render_template("index.html", rec_items=rec_items, trend_items=trend_items)


@main.route("/search")
def search():
    q = request.args.get('q', '').strip()
    filter_type = request.args.get('type', 'all')
    results = []

    if q:
        # log search for authenticated users (used to personalise recommendations)
        if current_user.is_authenticated:
            db.session.add(SearchHistory(
                user_id=current_user.id,
                search_query=q,
                result_type=filter_type if filter_type != 'all' else None,
            ))
            db.session.commit()

        if filter_type in ('all', 'book'):
            from recommender.api_clients.books_client import get_book_cover
            df = current_app.recommender.df
            mask = (df['Book'].str.contains(q, case=False, na=False) |
                    df['Author'].str.contains(q, case=False, na=False))
            book_results = []
            for _, row in df[mask].head(15).iterrows():
                book_results.append({
                    'type':      'book',
                    'title':     row['Book'],
                    'subtitle':  row['Author'],
                    'rating':    row['Avg_Rating'],
                    'url':       url_for('books.detail', title=row['Book']),
                    'poster_url': None,
                })
            if book_results:
                with ThreadPoolExecutor(max_workers=min(8, len(book_results))) as ex:
                    cover_futures = {ex.submit(get_book_cover, b['title']): b for b in book_results}
                for f, b in cover_futures.items():
                    b['poster_url'] = f.result()
            results.extend(book_results)

        if filter_type in ('all', 'movie'):
            for m in search_movies(q, max_results=15):
                results.append({
                    'type':      'movie',
                    'title':     m['title'],
                    'subtitle':  (m.get('description') or '')[:80],
                    'rating':    m.get('rating'),
                    'url':       url_for('movies.detail', title=m['title']),
                    'poster_url': m.get('poster_url'),
                })

    return render_template('search_result.html', results=results, query=q, filter_type=filter_type,
                           title=('Search: ' + q) if q else 'Search')


def _personalized_movie_items(top_n=20):
    """Return personalized movie items for authenticated users, trending otherwise."""
    if current_user.is_authenticated:
        movie_rows    = UserMovie.query.filter_by(user_id=current_user.id).all()
        wishlist_rows = WishListItem.query.filter_by(user_id=current_user.id).all()
        genres = [r.value for r in UserPreference.query.filter_by(
            user_id=current_user.id, pref_type='genre').all()]

        watched_titles        = [r.movie_title for r in movie_rows if r.status == 'watched']
        wishlist_movie_titles = [w.title for w in wishlist_rows if w.item_type == 'movie']
        recent_searches       = (SearchHistory.query
                                 .filter_by(user_id=current_user.id)
                                 .order_by(SearchHistory.searched_at.desc())
                                 .limit(10).all())
        search_queries = [s.search_query for s in recent_searches]
        favorites = (watched_titles + wishlist_movie_titles + search_queries)[:3]

        if favorites or genres:
            raw = get_movie_recommendations(favorites=favorites, genres=genres, max_results=top_n)
            return [_norm_movie(m) for m in raw]

    return get_trending_movies(top_n)


def _csv_fallback_books(top_n=20):
    """Return cached CSV fallback books instantly. Never blocks — returns [] on cache miss."""
    from recommender import cache
    cached = cache.get("csv_fallback_books")
    return cached[:top_n] if cached else []


def _build_csv_fallback_cache(app):
    """Background worker: fetch covers for top CSV books and store in cache."""
    from recommender import cache
    from recommender.api_clients.books_client import get_book_cover
    if cache.get("csv_fallback_books") is not None:
        return
    with app.app_context():
        df = app.recommender.df
        popular = (df[df['Avg_Rating'].notna()]
                   .sort_values('Avg_Rating', ascending=False)
                   .drop_duplicates('Book')
                   .head(40)
                   [['Book', 'Author', 'Avg_Rating', 'Genres_Clean']]
                   .to_dict('records'))
        if not popular:
            return
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(get_book_cover, row['Book']): row for row in popular}
            results = []
            for f in as_completed(futures):
                cover = f.result()
                if not cover:
                    continue
                row = futures[f]
                genres = [g.strip() for g in (row.get('Genres_Clean') or '').split(',') if g.strip()]
                results.append({
                    'title':        row['Book'],
                    'authors':      [row['Author']],
                    'rating':       row['Avg_Rating'],
                    'genres':       genres[:2],
                    'thumbnail':    cover,
                    'description':  '',
                    'year':         None,
                    'rating_count': None,
                    'info_link':    None,
                })
                if len(results) >= 20:
                    break
        if results:
            cache.set("csv_fallback_books", results, timeout=3600)


def _personalized_book_items(top_n=20):
    """Return personalized ML book items for authenticated users, popular otherwise."""
    from recommender.api_clients.books_client import get_book_cover
    if current_user.is_authenticated:
        book_rows     = UserBook.query.filter_by(user_id=current_user.id).all()
        wishlist_rows = WishListItem.query.filter_by(user_id=current_user.id).all()
        genres = [r.value for r in UserPreference.query.filter_by(
            user_id=current_user.id, pref_type='genre').all()]

        book_interactions = [{"title": r.book_title, "status": r.status, "rating": r.rating}
                             for r in book_rows]
        existing = {b['title'] for b in book_interactions}
        for w in wishlist_rows:
            if w.item_type == 'book' and w.title not in existing:
                book_interactions.append({"title": w.title, "status": "saved", "rating": None})

        raw    = current_app.recommender.get_personalized(book_interactions, genres, top_n=top_n + 10)
        normed = [_norm_book(b) for b in raw]

        # Fetch all missing covers simultaneously instead of one at a time
        need_cover = [b for b in normed if not b.get('thumbnail')]
        if need_cover:
            with ThreadPoolExecutor(max_workers=min(8, len(need_cover))) as ex:
                futures = {ex.submit(get_book_cover, b['title']): b for b in need_cover}
                for f in as_completed(futures):
                    futures[f]['thumbnail'] = f.result()

        books, seen = [], set()
        for b in normed:
            if b['title'] in seen or not b.get('thumbnail'):
                continue
            seen.add(b['title'])
            books.append(b)
            if len(books) >= top_n:
                break
        return books

    api_books = [_norm_book(b) for b in get_book_recommendations(max_results=top_n)]
    return api_books or _csv_fallback_books(top_n)


@main.route("/recommendations")
def recommendations():
    ccrc = copy_current_request_context
    uid  = current_user.id if current_user.is_authenticated else None
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_movies = ex.submit(ccrc(lambda: _cached_personalized_movie_items(uid, 20)))
        f_books  = ex.submit(ccrc(lambda: _cached_personalized_book_items(uid, 20)))
    movies_raw = f_movies.result()
    books_raw  = f_books.result()

    items = ([{"kind": "movie", **m} for m in movies_raw] +
             [{"kind": "book",  **b} for b in books_raw])
    random.shuffle(items)

    return render_template('browse.html', items=items, filter_type='all',
                           page_title='Recommendations', title='Recommendations')


@main.route("/trending")
def trending():
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_movies = ex.submit(get_trending_movies, 20)
        f_books  = ex.submit(get_trending_books, 20)
    movies_raw = [_norm_movie(m) for m in f_movies.result()]
    books_raw  = [_norm_book(b) for b in f_books.result()]
    if not books_raw:
        uid = current_user.id if current_user.is_authenticated else None
        books_raw = _cached_personalized_book_items(uid, 20) or _csv_fallback_books(20)

    items = ([{"kind": "movie", **m} for m in movies_raw] +
             [{"kind": "book",  **b} for b in books_raw])
    random.shuffle(items)

    return render_template('browse.html', items=items, filter_type='all',
                           page_title='Trending', title='Trending')


@main.route("/browse")
def top_recommendations():
    filter_type = request.args.get('type', 'all')
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_movies = ex.submit(get_trending_movies, 20)
        f_books  = ex.submit(get_book_recommendations, max_results=20)
    movies_raw = f_movies.result()
    books_raw  = f_books.result()
    if not books_raw:
        uid = current_user.id if current_user.is_authenticated else None
        books_raw = _cached_personalized_book_items(uid, 20) or _csv_fallback_books(20)

    items = ([{"kind": "movie", **_norm_movie(m)} for m in movies_raw] +
             [{"kind": "book",  **_norm_book(b)}  for b in books_raw])
    random.shuffle(items)

    return render_template('browse.html', items=items, filter_type=filter_type,
                           page_title='Top Recommendations', title='Top Recommendations')
