from flask import render_template, Blueprint, abort
from flask_login import current_user
from recommender.models import Comment, WishListItem
from recommender.api_clients.movies_client import get_movie
from recommender.api_clients.books_client import get_book

details = Blueprint('details', __name__)

@details.route("/<item_type>/<item_id>")
def detail(item_type, item_id):
    if item_type == 'movie':
        item = get_movie(item_id)
    elif item_type == 'book':
        item = get_book(item_id)
    else:
        abort(404)
    if item is None:
        abort(404)
    item['type'] = item_type
    in_wishlist = False
    if current_user.is_authenticated:
        in_wishlist = WishListItem.query.filter_by(
            user_id=current_user.id, item_type=item_type, item_id=item_id
        ).first() is not None
    comments = Comment.query.filter_by(item_type=item_type, item_id=item_id).all()
    return render_template("details.html", item=item, item_type=item_type,
                           comments=comments, in_wishlist=in_wishlist)

