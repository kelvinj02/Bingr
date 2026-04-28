from flask import render_template, Blueprint, current_app
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