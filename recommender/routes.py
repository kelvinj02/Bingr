from flask import render_template, url_for, flash, redirect
from recommender import app
from recommender.forms import RegistrationForm, LoginForm

@app.route("/")
@app.route("/home")
def home():
    return "<h1>Hello World</h1>"
    #return render_template("index.html")

@app.route("/signup", methods=['GET', 'POST'])
def signup():
    form=RegistrationForm()
    if form.validate_on_submit():
        flash("Your account has been created successfully!", "success")
        return redirect(url_for('home'))
    return render_template("register.html", title="Sign Up", form=form)

@app.route("/login", methods=['GET', 'POST'])
def login():
    form=LoginForm()
    # if form.validate_on_submit():
    #     if form.email.data == "example@gmail.com" and form.password.data == 'password':
    #         flash("You have been login!", "success")
    #     else:
    #         flash("Login Unsuccessful. Please check email and password", "danger")
    return render_template("login.html", title="Login", form=form)