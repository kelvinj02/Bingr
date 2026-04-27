from flask import render_template, Blueprint, abort
from recommender.models import Comment
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
    comments = Comment.query.filter_by(item_type=item_type, item_id=item_id).all()
    return render_template("details.html", item=item, item_type=item_type, comments=comments)

