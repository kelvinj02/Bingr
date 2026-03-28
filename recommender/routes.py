from flask import render_template
from recommender import app

@app.route("/")
@app.route("/home")
def home():
    return "<h1>Hello World</h1>"
    #return render_template("index.html")