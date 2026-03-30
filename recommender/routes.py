from flask import render_template, url_for, flash, redirect
from recommender import app, db, bcrypt
from recommender.forms import RegistrationForm, LoginForm
from recommender.models import User, Comment, WishListItem
from flask_login import login_user, current_user, logout_user

@app.route("/")
@app.route("/home")
def home():
    return "<h1>Hello World</h1>"
    #return render_template("index.html")

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
            return redirect(url_for('home'))
        else:
            flash("Login Unsuccessful. Please check email and password", "danger")
    return render_template("login.html", title="Login", form=form)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))