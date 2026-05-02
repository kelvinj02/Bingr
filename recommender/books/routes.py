from flask import Blueprint, render_template, request, redirect, url_for, abort, jsonify, flash, current_app
from flask_login import login_required, current_user
from recommender import db
from recommender.models import UserBook, UserPreference, Comment, WishListItem
from recommender.reviews.forms import CommentForm

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
    return (row.status, row.rating) if row else (None, None)


def _book_in_wishlist(title):
    if not current_user.is_authenticated:
        return False
    return bool(WishListItem.query.filter_by(
        user_id=current_user.id, item_type='book', item_id=title[:50]).first())


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

    return render_template('recommendations.html', books=recs, mode=mode, statuses=statuses,
                           title='Book Recommendations')


# /books/wishlist must be defined BEFORE /books/<path:title>
@books.route('/books/wishlist', methods=['POST'])
@login_required
def wishlist_toggle():
    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="Invalid JSON"), 400

    title = data.get('title', '').strip()
    if not title:
        return jsonify(error="title is required"), 400

    item_id  = title[:50]
    existing = WishListItem.query.filter_by(
        user_id=current_user.id, item_type='book', item_id=item_id).first()

    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify(ok=True, in_wishlist=False)

    db.session.add(WishListItem(
        user_id=current_user.id,
        item_type='book',
        item_id=item_id,
        title=title[:60],
    ))
    db.session.commit()
    return jsonify(ok=True, in_wishlist=True)


@books.route('/books/<path:title>', methods=['GET', 'POST'])
def detail(title):
    from recommender.api_clients.books_client import (
        get_book_cover, get_book_by_title, get_book_characters
    )
    df = current_app.recommender.df
    matches = df[df['Book'] == title]

    if matches.empty:
        book_data = get_book_by_title(title)
        if book_data:
            cover_url = book_data.pop('_cover_url', None)
            book      = book_data
        else:
            # API unavailable — show a minimal page rather than 404
            book      = {'Book': title, 'Author': '', 'Avg_Rating': None,
                         'Num_Ratings': None, 'Description': '', 'Genres_Clean': '', 'URL': ''}
            cover_url = None
        similar = []
    else:
        book      = matches.iloc[0].to_dict()
        similar   = current_app.recommender.get_similar(title, top_n=10)
        cover_url = get_book_cover(title)

    characters    = get_book_characters(title)
    comments      = Comment.query.filter_by(
        item_type='book', item_id=title).order_by(Comment.created_at.desc()).all()
    in_wishlist   = _book_in_wishlist(title)
    status, user_rating = _user_book_status(title)

    form = CommentForm() if current_user.is_authenticated else None
    if form and form.validate_on_submit():
        db.session.add(Comment(
            user_id=current_user.id,
            item_type='book',
            item_id=title,
            review_score=form.review_score.data,
            content=form.body.data,
        ))
        db.session.commit()
        flash('Review posted!', 'success')
        return redirect(url_for('books.detail', title=title))

    return render_template('book_details.html', book=book, similar=similar,
                           in_wishlist=in_wishlist, user_status=status,
                           user_rating=user_rating, cover_url=cover_url,
                           characters=characters, comments=comments, form=form,
                           title=book['Book'])


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
            "title":       row['Book'],
            "author":      row['Author'],
            "genres":      row['Genres_Clean'],
            "avg_rating":  row['Avg_Rating'],
            "url":         row['URL'],
            "user_status": status,
            "user_rating": rating,
        })
    return render_template('search_result.html', books=books_list, query=q)
