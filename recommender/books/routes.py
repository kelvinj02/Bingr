from flask import Blueprint, render_template, request, redirect, url_for, abort, jsonify, current_app
from flask_login import login_required, current_user
from recommender import db
from recommender.models import UserBook, UserPreference

books = Blueprint('books', __name__)


def _get_interactions():
    rows = UserBook.query.filter_by(user_id=current_user.id).all()
    return [{"title": r.book_title, "status": r.status, "rating": r.rating} for r in rows]


def _get_genres():
    rows = UserPreference.query.filter_by(user_id=current_user.id, pref_type='genre').all()
    return [r.value for r in rows]


def _user_book_status(title):
    if not current_user.is_authenticated:
        return None, None
    row = UserBook.query.filter_by(user_id=current_user.id, book_title=title).first()
    if row:
        return row.status, row.rating
    return None, None


@books.route('/recommendations')
@login_required
def recommendations():
    interactions = _get_interactions()
    genres = _get_genres()
    recs = current_app.recommender.get_personalized(interactions, genres, top_n=50)
    mode = "Based on your taste" if len(interactions) >= 3 else "Top picks for you"

    interacted_titles = {i["title"] for i in interactions}
    statuses = {}
    if interacted_titles:
        rows = UserBook.query.filter(
            UserBook.user_id == current_user.id,
            UserBook.book_title.in_(interacted_titles)
        ).all()
        statuses = {r.book_title: (r.status, r.rating) for r in rows}

    return render_template('recommendations.html', books=recs, mode=mode, statuses=statuses)


@books.route('/books/<path:title>')
def detail(title):
    df = current_app.recommender.df
    matches = df[df['Book'] == title]
    if matches.empty:
        abort(404)
    book = matches.iloc[0].to_dict()
    similar = current_app.recommender.get_similar(title, top_n=5)
    status, rating = _user_book_status(title)
    from recommender.api_clients.books_client import get_book_cover
    cover_url = get_book_cover(title)
    return render_template('book_details.html', book=book, similar=similar,
                           user_status=status, user_rating=rating, cover_url=cover_url)


@books.route('/search')
def search():
    q = request.args.get('q', '').strip()
    if not q:
        return redirect(url_for('main.home'))
    df = current_app.recommender.df
    mask = (
        df['Book'].str.contains(q, case=False, na=False) |
        df['Author'].str.contains(q, case=False, na=False)
    )
    results = df[mask].head(20)
    books_list = []
    for _, row in results.iterrows():
        status, rating = _user_book_status(row['Book'])
        books_list.append({
            "title": row['Book'],
            "author": row['Author'],
            "genres": row['Genres_Clean'],
            "avg_rating": row['Avg_Rating'],
            "url": row['URL'],
            "user_status": status,
            "user_rating": rating,
        })
    return render_template('search_result.html', books=books_list, query=q)


@books.route('/books/interact', methods=['POST'])
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
    if action not in ('save', 'read'):
        return jsonify(error="action must be 'save' or 'read'"), 400
    if rating is not None:
        try:
            rating = int(rating)
        except (ValueError, TypeError):
            return jsonify(error="rating must be an integer"), 400
        if rating not in (1, 2, 3, 4, 5):
            return jsonify(error="rating must be between 1 and 5"), 400

    if title not in current_app.recommender.title_to_idx:
        return jsonify(error="book not found"), 404

    row = UserBook.query.filter_by(user_id=current_user.id, book_title=title).first()

    if action == 'save':
        if row is None:
            db.session.add(UserBook(user_id=current_user.id, book_title=title, status='saved'))
        elif row.status == 'saved':
            db.session.delete(row)
            db.session.commit()
            return jsonify(ok=True, status='removed', rating=None)
        # row.status == 'read' → no-op, read always wins
    elif action == 'read':
        if row is None:
            db.session.add(UserBook(user_id=current_user.id, book_title=title,
                                    status='read', rating=rating))
        else:
            row.status = 'read'
            row.rating = rating

    db.session.commit()
    updated = UserBook.query.filter_by(user_id=current_user.id, book_title=title).first()
    return jsonify(ok=True, status=updated.status if updated else 'removed',
                   rating=updated.rating if updated else None)
