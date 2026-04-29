from flask import render_template, url_for, flash, redirect, Blueprint, request, abort
from flask_login import current_user, login_required
from recommender.reviews.forms import CommentForm
from recommender import db
from recommender.models import Comment

reviews = Blueprint('reviews', __name__)

#Create comment
@reviews.route("/comment/<item_type>/<item_id>", methods=['GET', 'POST']) 
@login_required
def comment(item_type, item_id):
    if item_type not in ('movie', 'book'):
        abort(404)
    form=CommentForm()
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("Please log in to post a review.", "warning")
            return redirect(url_for("users.login"))
        else:
            new_comment = Comment(
                user_id=current_user.id,
                item_type=item_type,
                item_id=item_id,
                review_score=form.review_score.data,
                content=form.body.data
            )
            db.session.add(new_comment)
            db.session.commit()
            flash("Your review has been posted!", "success")
            return redirect(url_for('details.detail', item_type=item_type, item_id=item_id))
    return render_template("comment.html", title="New Comment", form=form)

#Update comment
@reviews.route("/comment/<int:comment_id>/update", methods=['GET', 'POST'])
@login_required
def update_comment(comment_id):
    comment= Comment.query.get_or_404(comment_id)
    if comment.user_id != current_user.id:
        abort(403)
    form= CommentForm()
    if form.validate_on_submit():
        comment.review_score = form.review_score.data
        comment.content = form.body.data
        db.session.commit()
        flash("Your review has been updated!", "success")
        next_url = request.args.get('next') or request.form.get('next')
        return redirect(next_url or url_for('details.detail', item_type=comment.item_type, item_id=comment.item_id))
    elif request.method == 'GET':
        form.review_score.data = comment.review_score
        form.body.data = comment.content
    return render_template("comment.html", title="Update Comment", form=form)

#Delete comment
@reviews.route("/comment/<int:comment_id>/delete", methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.user_id != current_user.id:
        abort(403)
    item_type = comment.item_type
    item_id = comment.item_id
    db.session.delete(comment)
    db.session.commit()
    flash("Your review has been deleted.", "info")
    next_url = request.args.get('next') or request.form.get('next')
    return redirect(next_url or url_for('details.detail', item_type=item_type, item_id=item_id))