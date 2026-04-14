from flask import render_template, url_for, flash, redirect, request
from recommender import app, db, bcrypt, mail
from recommender.forms import RegistrationForm, LoginForm, CommentForm, RequestResetForm, ResetPasswordForm
from recommender.models import User, Comment, WishListItem
from flask_login import login_user, current_user, logout_user, login_required
from flask_mail import Message

@app.route("/")
@app.route("/home")
def home():
    return render_template("index.html")

@app.route("/signup", methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:   #redirect to home page if user is already login
        return redirect(url_for('home'))
    form=RegistrationForm()
    if form.validate_on_submit():
        #get a hash string for password instead of byte using decode
        hashed_password= bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user=User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)    #adding user to database
        db.session.commit()     #commit change in database
        flash("Your account has been created successfully!", "success")
        return redirect(url_for('login'))
    return render_template("register.html", title="Sign Up", form=form)

@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form=LoginForm()
    if form.validate_on_submit():
        user=User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page=request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash("Login Unsuccessful. Please check email and password", "danger")
    return render_template("login.html", title="Login", form=form)

@app.route("/account")
@login_required
def account():
    return render_template("account.html", title="account")

@app.route("/comment") #comment session in detail, will change the route location later
@login_required
def comment():
    form=CommentForm()
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("Please log in to post a review.", "warning")
            return redirect(url_for("login"))
    return render_template("comment.html", title="New Comment", form=form)

#need to add: delete comment, update comment (routes)

def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Password Reset Request', sender='noreply@demo.com', recipients=[user.email])
    msg.body = f"""To reset your password, visit to the following link:
{url_for('reset_token', token=token, _external=True)}

If you did not make this request then simply ignore this message and no changes will be made. 
"""
    mail.send(msg)
    
#the route where the users enter their email to request to reset password
@app.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    #make sure if the user is logout
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form=RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        send_reset_email(user)
        flash('Check your email to reset your password.', 'info')
        return redirect(url_for('login'))
    return render_template('reset_request.html', title="Reset Password", form=form)

#the route where the users actually reset their password
#by sending them email with the token
@app.route("/reset_password/<token>", methods=['GET','POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    user=User.verify_reset_token(token)
    if user is None:
        flash('That is an expired or invalid token.', 'warning')
        return redirect(url_for('reset_request'))
    form=ResetPasswordForm()
    if form.validate_on_submit():
        #get a hash string for password instead of byte using decode
        hashed_password= bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.password = hashed_password    #adding user password to database
        db.session.commit()     #commit change in database
        flash("Your password has been updated! You are now able to log in", "success")
        return redirect(url_for('login'))
    return render_template('reset_token.html', title='Reset Password', form=form)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))