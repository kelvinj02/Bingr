from flask import render_template, url_for, flash, redirect, request, Blueprint, abort
from flask_login import login_user, current_user, logout_user, login_required
from recommender import db, bcrypt
from recommender.models import User, WishListItem
from recommender.users.forms import (RegistrationForm, LoginForm, RequestResetForm, ResetPasswordForm)
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
        flash("Your account has been created successfully!", "success")
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

@users.route("/account")
@login_required
def account():
    return render_template("account.html", title="account")

#the route where the users enter their email to request to reset password
@users.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    #make sure if the user is logout
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    form=RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        send_reset_email(user)
        flash('Check your email to reset your password.', 'info')
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

@users.route("/search")
def search():
    return render_template('search_result.html', title='Search Result')

#View Wishlist
@users.route("/wishlist", methods=['GET'])
@login_required
def wishlist():
    items = WishListItem.query.filter_by(user_id=current_user.id).all()
    return render_template("wishlist.html", title="My Wishlist", items=items)

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
    return redirect(url_for('details.detail', item_type=item_type, item_id=item_id))

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

@users.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('main.home'))
