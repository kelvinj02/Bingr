from flask import render_template, Blueprint, request, url_for, current_app
from flask_login import current_user
from recommender.models import UserBook, UserPreference

main = Blueprint('main', __name__)

@main.route("/")
@main.route("/home")
def home():
    preview_books = []
    if current_user.is_authenticated:
        interactions = [
            {"title": r.book_title, "status": r.status, "rating": r.rating}
            for r in UserBook.query.filter_by(user_id=current_user.id).all()
        ]
        genres = [
            r.value for r in
            UserPreference.query.filter_by(user_id=current_user.id, pref_type='genre').all()
        ]
        preview_books = current_app.recommender.get_personalized(interactions, genres, top_n=5)
    preview_movies = current_app.movie_recommender.get_popular(top_n=5)
    return render_template("index.html", preview_books=preview_books, preview_movies=preview_movies)

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
    books, movies = [], []
    if filter_type in ('all', 'book'):
        if current_user.is_authenticated:
            interactions = [
                {"title": r.book_title, "status": r.status, "rating": r.rating}
                for r in UserBook.query.filter_by(user_id=current_user.id).all()
            ]
            genres = [
                r.value for r in
                UserPreference.query.filter_by(user_id=current_user.id, pref_type='genre').all()
            ]
            books = current_app.recommender.get_personalized(interactions, genres, top_n=20)
        else:
            books = current_app.recommender.get_cold_start([], top_n=20)
    if filter_type in ('all', 'movie'):
        movies = current_app.movie_recommender.get_popular(top_n=20)
    return render_template('browse.html', books=books, movies=movies, filter_type=filter_type)