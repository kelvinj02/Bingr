from flask import render_template, url_for, flash, redirect, Blueprint
from flask_login import current_user, login_required
from recommender.reviews.forms import CommentForm

reviews = Blueprint('reviews', __name__)

@reviews.route("/comment") #comment session in detail, will change the route location later
@login_required
def comment():
    form=CommentForm()
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("Please log in to post a review.", "warning")
            return redirect(url_for("users.login"))
    return render_template("comment.html", title="New Comment", form=form)

#need to add: delete comment, update comment (routes)