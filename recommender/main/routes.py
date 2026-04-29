import random
from flask import render_template, Blueprint, request, url_for, current_app
from flask_login import current_user
from recommender import db
from recommender.models import UserBook, UserMovie, UserPreference, WishListItem, SearchHistory
from recommender.api_clients.movies_client import get_trending_movies, get_movie_recommendations, search_movies
from recommender.api_clients.books_client import get_book_recommendations

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


@main.route("/")
@main.route("/home")
def home():
    all_trending = get_trending_movies(10)

    rec_movies_raw = _personalized_movie_items(top_n=5)
    rec_books_raw  = _personalized_book_items(top_n=5)

    trend_movies_raw = all_trending[5:]
    trend_books_raw  = [_norm_book(b) for b in get_book_recommendations(max_results=5)]

    rec_items = ([{"kind": "movie", **m} for m in rec_movies_raw] +
                 [{"kind": "book",  **b} for b in rec_books_raw])
    random.shuffle(rec_items)

    trend_items = ([{"kind": "movie", **_norm_movie(m)} for m in trend_movies_raw] +
                   [{"kind": "book",  **b} for b in trend_books_raw])
    random.shuffle(trend_items)

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
            df = current_app.recommender.df
            mask = (df['Book'].str.contains(q, case=False, na=False) |
                    df['Author'].str.contains(q, case=False, na=False))
            for _, row in df[mask].head(15).iterrows():
                results.append({
                    'type':      'book',
                    'title':     row['Book'],
                    'subtitle':  row['Author'],
                    'rating':    row['Avg_Rating'],
                    'url':       url_for('books.detail', title=row['Book']),
                    'poster_url': None,  # template falls back to Open Library
                })

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

    return render_template('search_result.html', results=results, query=q, filter_type=filter_type)


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


def _personalized_book_items(top_n=20):
    """Return personalized ML book items for authenticated users, popular otherwise."""
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

        raw = current_app.recommender.get_personalized(book_interactions, genres, top_n=top_n)
        return [_norm_book(b) for b in raw]

    return [_norm_book(b) for b in get_book_recommendations(max_results=top_n)]


@main.route("/recommendations")
def recommendations():
    movies_raw = _personalized_movie_items(top_n=20)
    books_raw  = _personalized_book_items(top_n=20)

    items = ([{"kind": "movie", **m} for m in movies_raw] +
             [{"kind": "book",  **b} for b in books_raw])
    random.shuffle(items)

    return render_template('browse.html', items=items, filter_type='all',
                           page_title='Recommendations')


@main.route("/trending")
def trending():
    movies_raw = get_trending_movies(20)
    books_raw  = [_norm_book(b) for b in get_book_recommendations(max_results=20)]

    items = ([{"kind": "movie", **_norm_movie(m)} for m in movies_raw] +
             [{"kind": "book",  **b} for b in books_raw])
    random.shuffle(items)

    return render_template('browse.html', items=items, filter_type='all',
                           page_title='Trending')


@main.route("/browse")
def top_recommendations():
    filter_type = request.args.get('type', 'all')

    movies_raw = get_trending_movies(20)
    books_raw  = get_book_recommendations(max_results=20)

    items = ([{"kind": "movie", **_norm_movie(m)} for m in movies_raw] +
             [{"kind": "book",  **_norm_book(b)}  for b in books_raw])
    random.shuffle(items)

    return render_template('browse.html', items=items, filter_type=filter_type,
                           page_title='Top Recommendations')
