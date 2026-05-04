from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, render_template, request, redirect, url_for, abort, jsonify, flash, current_app
from flask_login import login_required, current_user
from recommender import db
from recommender.models import UserMovie, Comment, WishListItem
from recommender.reviews.forms import CommentForm
from recommender.api_clients.movies_client import get_movie_poster, get_movie_full, search_movie_by_title

movies = Blueprint('movies', __name__, url_prefix='/movies')


def _user_movie_status(title):
    if not current_user.is_authenticated:
        return None, None
    row = UserMovie.query.filter_by(user_id=current_user.id, movie_title=title).first()
    return (row.status, row.rating) if row else (None, None)


def _in_wishlist(movie_id):
    if not current_user.is_authenticated:
        return False
    return bool(WishListItem.query.filter_by(
        user_id=current_user.id, item_type='movie', item_id=str(movie_id)).first())


@movies.route('/recommendations')
@login_required
def recommendations():
    from recommender.api_clients.movies_client import get_movie_poster as gmp
    interactions = [{"title": r.movie_title, "status": r.status}
                    for r in UserMovie.query.filter_by(user_id=current_user.id).all()]
    recs = current_app.movie_recommender.get_personalized(interactions, top_n=20)
    if recs:
        with ThreadPoolExecutor(max_workers=min(10, len(recs))) as ex:
            poster_futures = [(movie, ex.submit(gmp, movie['movie_id'])) for movie in recs]
        for movie, f in poster_futures:
            movie['poster_url'] = f.result()
    mode = "Based on your taste" if interactions else "Popular Movies"
    return render_template('movie_recommendations.html', movies=recs, mode=mode,
                           title='Movie Recommendations')


@movies.route('/search')
def search():
    q = request.args.get('q', '').strip()
    if not q:
        return redirect(url_for('main.home'))
    from recommender.api_clients.movies_client import search_movies
    results = search_movies(q, max_results=20)
    return render_template('movie_search_result.html', movies=results, query=q,
                           title=('Search: ' + q) if q else 'Movie Search')


# /wishlist and /interact must be defined BEFORE /<path:title>
@movies.route('/wishlist', methods=['POST'])
@login_required
def wishlist_toggle():
    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="Invalid JSON"), 400

    movie_id = data.get('movie_id')
    title    = data.get('title', '').strip()

    if not movie_id or not title:
        return jsonify(error="movie_id and title are required"), 400

    item_id = str(movie_id)
    existing = WishListItem.query.filter_by(
        user_id=current_user.id, item_type='movie', item_id=item_id).first()

    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify(ok=True, in_wishlist=False)

    db.session.add(WishListItem(
        user_id=current_user.id,
        item_type='movie',
        item_id=item_id,
        title=title[:60],
    ))
    db.session.commit()
    return jsonify(ok=True, in_wishlist=True)


@movies.route('/<path:title>', methods=['GET', 'POST'])
def detail(title):
    df = current_app.movie_recommender.df
    matches = df[df['title'] == title]

    if not matches.empty:
        movie_id     = int(matches.iloc[0]['movie_id'])
        similar_raw  = current_app.movie_recommender.get_similar(title, top_n=10)
    else:
        movie_id = search_movie_by_title(title)
        if not movie_id:
            abort(404)
        similar_raw = []

    movie = get_movie_full(movie_id)
    if not movie:
        abort(404)

    if not similar_raw:
        from recommender.api_clients.movies_client import _get_similar_movies, _format_movie
        raw_sim = _get_similar_movies(movie_id, 10)
        similar = []
        for s in raw_sim:
            fmt = _format_movie(s, [], None)
            similar.append({"title": fmt["title"], "poster_url": fmt["thumbnail"],
                            "overview": fmt["description"]})
    else:
        with ThreadPoolExecutor(max_workers=min(10, len(similar_raw))) as ex:
            poster_futures = [(s, ex.submit(get_movie_poster, s["movie_id"])) for s in similar_raw]
        similar = [{"title": s["title"], "poster_url": f.result(),
                    "overview": s.get("overview", "")}
                   for s, f in poster_futures]

    in_wishlist   = _in_wishlist(movie_id)
    status, user_rating = _user_movie_status(title)
    comments = Comment.query.filter_by(
        item_type='movie', item_id=movie['id']).order_by(Comment.created_at.desc()).all()

    form = CommentForm() if current_user.is_authenticated else None
    if form and form.validate_on_submit():
        db.session.add(Comment(
            user_id=current_user.id,
            item_type='movie',
            item_id=movie['id'],
            review_score=form.review_score.data,
            content=form.body.data,
        ))
        db.session.commit()
        flash('Review posted!', 'success')
        return redirect(url_for('movies.detail', title=title))

    return render_template('movie_details.html', movie=movie, similar=similar,
                           in_wishlist=in_wishlist, user_status=status,
                           user_rating=user_rating, comments=comments, form=form,
                           title=movie['title'])
