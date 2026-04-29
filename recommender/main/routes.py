import random
from flask import render_template, Blueprint, request, url_for, current_app
from flask_login import current_user
from recommender.models import UserBook, UserPreference
from recommender.api_clients.movies_client import get_trending_movies
from recommender.api_clients.books_client import get_book_recommendations

main = Blueprint('main', __name__)

@main.route("/")
@main.route("/home")
def home():
    # fetch 10 trending movies once, split between sections so they differ
    all_movies = get_trending_movies(10)
    rec_movies_raw  = all_movies[:5]
    trend_movies_raw = all_movies[5:]

    # personalized books for Recommendations; general popular for Trending
    if current_user.is_authenticated:
        genres = [
            r.value for r in
            UserPreference.query.filter_by(user_id=current_user.id, pref_type='genre').all()
        ]
        rec_books_raw = get_book_recommendations(genres=genres, max_results=5)
    else:
        rec_books_raw = get_book_recommendations(max_results=5)

    trend_books_raw = get_book_recommendations(max_results=5)

    rec_items = [{"kind": "movie", **m} for m in rec_movies_raw] + \
                [{"kind": "book",  **b} for b in rec_books_raw]
    random.shuffle(rec_items)

    trend_items = [{"kind": "movie", **m} for m in trend_movies_raw] + \
                  [{"kind": "book",  **b} for b in trend_books_raw]
    random.shuffle(trend_items)

    return render_template("index.html", rec_items=rec_items, trend_items=trend_items)

@main.route("/search")
def search():
    q = request.args.get('q', '').strip()
    filter_type = request.args.get('type', 'all')
    results = []
    if q:
        if filter_type in ('all', 'book'):
            df = current_app.recommender.df
            mask = (df['Book'].str.contains(q, case=False, na=False) |
                    df['Author'].str.contains(q, case=False, na=False))
            for _, row in df[mask].head(15).iterrows():
                results.append({
                    'type': 'book',
                    'title': row['Book'],
                    'subtitle': row['Author'],
                    'rating': row['Avg_Rating'],
                    'url': url_for('books.detail', title=row['Book'])
                })
        if filter_type in ('all', 'movie'):
            df = current_app.movie_recommender.df
            mask = df['title'].str.contains(q, case=False, na=False)
            for _, row in df[mask].head(15).iterrows():
                results.append({
                    'type': 'movie',
                    'title': row['title'],
                    'subtitle': row['overview'][:80],
                    'url': url_for('movies.detail', title=row['title'])
                })
    return render_template('search_result.html', results=results, query=q, filter_type=filter_type)

@main.route("/browse")
def top_recommendations():
    filter_type = request.args.get('type', 'all')

    movies_raw = get_trending_movies(20)
    books_raw  = get_book_recommendations(max_results=20)

    items = [{"kind": "movie", **m} for m in movies_raw] + \
            [{"kind": "book",  **b} for b in books_raw]
    random.shuffle(items)

    return render_template('browse.html', items=items, filter_type=filter_type)