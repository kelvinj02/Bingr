from flask import Blueprint, render_template, request, redirect, url_for, abort, jsonify, current_app
from flask_login import login_required, current_user
from recommender import db
from recommender.models import UserMovie
from recommender.api_clients.movies_client import get_movie

movies = Blueprint('movies', __name__, url_prefix='/movies')


def _get_interactions():
    rows = UserMovie.query.filter_by(user_id=current_user.id).all()
    return [{"title": r.movie_title, "status": r.status} for r in rows]


def _user_movie_status(title):
    if not current_user.is_authenticated:
        return None, None
    row = UserMovie.query.filter_by(user_id=current_user.id, movie_title=title).first()
    if row:
        return row.status, row.rating
    return None, None


@movies.route('/recommendations')
@login_required
def recommendations():
    interactions = _get_interactions()
    recs = current_app.movie_recommender.get_personalized(interactions, top_n=20)
    for movie in recs:
        movie['poster_url'] = get_movie(movie['movie_id'])
    mode = "Based on your taste" if interactions else "Popular Movies"
    return render_template('movie_recommendations.html', movies=recs, mode=mode)


@movies.route('/search')
def search():
    q = request.args.get('q', '').strip()
    if not q:
        return redirect(url_for('main.home'))
    df = current_app.movie_recommender.df
    mask = df['title'].str.contains(q, case=False, na=False)
    results = df[mask].head(20)
    movies_list = []
    for _, row in results.iterrows():
        status, rating = _user_movie_status(row['title'])
        movies_list.append({
            'title':       row['title'],
            'movie_id':    int(row['movie_id']),
            'overview':    row['overview'],
            'poster_url':  get_movie_poster(int(row['movie_id'])),
            'user_status': status,
        })
    return render_template('movie_search_result.html', movies=movies_list, query=q)


@movies.route('/<path:title>')
def detail(title):
    df = current_app.movie_recommender.df
    matches = df[df['title'] == title]
    if matches.empty:
        abort(404)
    movie = matches.iloc[0].to_dict()
    movie['movie_id'] = int(movie['movie_id'])
    similar = current_app.movie_recommender.get_similar(title, top_n=5)
    poster_url = get_movie_poster(movie['movie_id'])
    status, rating = _user_movie_status(title)
    return render_template('movie_details.html', movie=movie, similar=similar,
                           poster_url=poster_url, user_status=status, user_rating=rating)


@movies.route('/interact', methods=['POST'])
@login_required
def interact():
    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="Invalid JSON"), 400

    title = data.get('title', '').strip()
    action = data.get('action', '').strip()
    rating = data.get('rating')

    if not title:
        return jsonify(error="title is required"), 400
    if action not in ('save', 'watched'):
        return jsonify(error="action must be 'save' or 'watched'"), 400
    if rating is not None:
        try:
            rating = int(rating)
        except (ValueError, TypeError):
            return jsonify(error="rating must be an integer"), 400
        if rating not in (1, 2, 3, 4, 5):
            return jsonify(error="rating must be between 1 and 5"), 400

    if title not in current_app.movie_recommender.title_to_idx:
        return jsonify(error="movie not found"), 404

    row = UserMovie.query.filter_by(user_id=current_user.id, movie_title=title).first()

    if action == 'save':
        if row is None:
            db.session.add(UserMovie(user_id=current_user.id, movie_title=title, status='saved'))
        elif row.status == 'saved':
            db.session.delete(row)
            db.session.commit()
            return jsonify(ok=True, status='removed', rating=None)
    elif action == 'watched':
        if row is None:
            db.session.add(UserMovie(user_id=current_user.id, movie_title=title,
                                     status='watched', rating=rating))
        else:
            row.status = 'watched'
            row.rating = rating

    db.session.commit()
    updated = UserMovie.query.filter_by(user_id=current_user.id, movie_title=title).first()
    return jsonify(ok=True, status=updated.status if updated else 'removed',
                   rating=updated.rating if updated else None)
