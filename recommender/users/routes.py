from flask import render_template, url_for, flash, redirect, request, Blueprint, abort, current_app
from flask_login import login_user, current_user, logout_user, login_required
from types import SimpleNamespace
from recommender import db, bcrypt
from recommender.models import User, WishListItem, UserPreference, Comment, UserBook, UserMovie
from recommender.users.forms import (RegistrationForm, LoginForm, RequestResetForm, ResetPasswordForm, UpdateAccountForm)
from recommender.users.utils import send_reset_email
users = Blueprint('users', __name__)

@users.route("/signup", methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:   #redirect to home page if user is already login
        return redirect(url_for('main.home'))
    form=RegistrationForm()
    if form.validate_on_submit():
        #get a hash string for password instead of byte using decode
        hashed_password= bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user=User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)    #adding user to database
        db.session.commit()     #commit change in database
        flash("Your account has been created successfully! Please log in.", "success")
        return redirect(url_for('users.login'))
    return render_template("register.html", title="Sign Up", form=form)

@users.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    form=LoginForm()
    if form.validate_on_submit():
        user=User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page=request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.home'))
        else:
            flash("Login Unsuccessful. Please check email and password", "danger")
    return render_template("login.html", title="Login", form=form)

@users.route("/account", methods=['GET', 'POST'])
@login_required
def account():
    form = UpdateAccountForm()
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Your account has been updated!', 'success')
        return redirect(url_for('users.account'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
    book_ratings  = UserBook.query.filter(UserBook.user_id == current_user.id,
                                           UserBook.rating.isnot(None)).all()
    movie_ratings = UserMovie.query.filter(UserMovie.user_id == current_user.id,
                                           UserMovie.rating.isnot(None)).all()

    ratings = []
    for r in book_ratings:
        ratings.append(SimpleNamespace(
            item_type='book', item_id=r.book_title, title=r.book_title,
            score=r.rating * 2, author=None, director=None,
        ))
    for r in movie_ratings:
        ratings.append(SimpleNamespace(
            item_type='movie', item_id=r.movie_title, title=r.movie_title,
            score=r.rating * 2, author=None, director=None,
        ))

    from recommender.api_clients.movies_client import get_movie_poster, get_movie_full
    from recommender.api_clients.books_client import get_book_cover

    raw_comments = Comment.query.filter_by(user_id=current_user.id).all()
    comments = []
    for c in raw_comments:
        if c.item_type == 'movie':
            try:
                mid = int(c.item_id)
                df = current_app.movie_recommender.df
                matches = df[df['movie_id'] == mid]
                if not matches.empty:
                    display_title = matches.iloc[0]['title']
                else:
                    movie_data = get_movie_full(mid)
                    display_title = movie_data['title'] if movie_data else c.item_id
            except Exception:
                display_title = c.item_id
                mid = None
            cover_url = get_movie_poster(mid) if mid else None
        else:
            display_title = c.item_id
            cover_url = get_book_cover(c.item_id)
        comments.append(SimpleNamespace(
            id=c.id, item_type=c.item_type, item_id=c.item_id,
            display_title=display_title, cover_url=cover_url,
            content=c.content, review_score=c.review_score, created_at=c.created_at,
        ))

    return render_template('account.html', title='Account', form=form,
                           ratings=ratings, comments=comments)

#the route where the users enter their email to request to reset password
@users.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    #make sure if the user is logout
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    form=RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        try:
            send_reset_email(user)
            flash('Check your email to reset your password.', 'info')
        except Exception as e:
            flash(f'Email failed: {e}', 'danger')
        return redirect(url_for('users.login'))
    return render_template('reset_request.html', title="Reset Password", form=form)

#the route where the users actually reset their password
#by sending them email with the token
@users.route("/reset_password/<token>", methods=['GET','POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    user=User.verify_reset_token(token)
    if user is None:
        flash('That is an expired or invalid token.', 'warning')
        return redirect(url_for('users.reset_request'))
    form=ResetPasswordForm()
    if form.validate_on_submit():
        #get a hash string for password instead of byte using decode
        hashed_password= bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.password = hashed_password    #adding user password to database
        db.session.commit()     #commit change in database
        flash("Your password has been updated! You are now able to log in", "success")
        return redirect(url_for('users.login'))
    return render_template('reset_token.html', title='Reset Password', form=form)

@users.route("/onboarding", methods=['GET', 'POST'])
@login_required
def onboarding():
    if request.args.get('skip'):
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        selected_genres = request.form.getlist('genres')
        raw_authors = request.form.get('authors', '').strip()
        authors = [a.strip() for a in raw_authors.split(',') if a.strip()]

        UserPreference.query.filter_by(user_id=current_user.id).delete()
        for genre in selected_genres:
            db.session.add(UserPreference(user_id=current_user.id, pref_type='genre', value=genre))
        for author in authors:
            db.session.add(UserPreference(user_id=current_user.id, pref_type='author', value=author))
        db.session.commit()
        return redirect(url_for('main.home'))

    genres = current_app.recommender.genres
    return render_template('onboarding.html', title='Set Your Preferences', genres=genres)


#View Wishlist
@users.route("/wishlist", methods=['GET'])
@login_required
def wishlist():
    from recommender.api_clients.movies_client import get_movie_poster
    items = WishListItem.query.filter_by(user_id=current_user.id).all()
    posters = {}
    for item in items:
        if item.item_type == 'movie':
            try:
                posters[item.id] = get_movie_poster(int(item.item_id))
            except (ValueError, TypeError):
                posters[item.id] = None
        else:
            posters[item.id] = None
    return render_template("wishlist.html", title="My Wishlist", items=items, posters=posters)

#Add items to Wishlist
@users.route("/wishlist/add/<item_type>/<item_id>", methods=['POST'])
@login_required
def add_to_wishlist(item_type, item_id):
    if item_type not in ('movie', 'book'):
        abort(404)
    existing = WishListItem.query.filter_by(user_id=current_user.id, item_type=item_type, item_id=item_id).first()
    if existing:
        flash("Already in your wishlist.", "info")
    else:
        item= WishListItem(
            user_id=current_user.id,
            item_type=item_type,
            item_id=item_id,
            title=request.form.get('title')
        )
        db.session.add(item)
        db.session.commit()
        flash("Added to wishlist!", "success")
    return redirect(url_for('users.wishlist'))

#Remove item from Wishlist
@users.route("/wishlist/remove/<int:item_id>", methods=['POST'])
@login_required
def remove_wishlist(item_id):
    item = WishListItem.query.get_or_404(item_id)
    if item.user_id != current_user.id:
        abort(403)
    db.session.delete(item)
    db.session.commit()
    flash("Removed from wishlist.", "info")
    return redirect(url_for('users.wishlist'))

@users.route("/account/update-username", methods=['POST'])
@login_required
def update_username():
    new_name = request.form.get('username', '').strip()
    if not new_name or not (3 <= len(new_name) <= 20):
        flash('Username must be between 3 and 20 characters.', 'danger')
        return redirect(url_for('users.account'))
    taken = User.query.filter_by(username=new_name).first()
    if taken and taken.id != current_user.id:
        flash('That username is already taken.', 'danger')
        return redirect(url_for('users.account'))
    current_user.username = new_name
    db.session.commit()
    flash('Username updated!', 'success')
    return redirect(url_for('users.account'))


@users.route("/account/delete", methods=['POST'])
@login_required
def delete_account():
    from recommender.models import SearchHistory
    user = current_user._get_current_object()
    Comment.query.filter_by(user_id=user.id).delete()
    WishListItem.query.filter_by(user_id=user.id).delete()
    SearchHistory.query.filter_by(user_id=user.id).delete()
    logout_user()
    db.session.delete(user)
    db.session.commit()
    flash('Your account has been deleted.', 'info')
    return redirect(url_for('main.home'))


@users.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('main.home'))
