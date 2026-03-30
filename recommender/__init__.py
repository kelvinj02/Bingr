from flask import Flask, Bcrypt
from flask_sqlalchemy import SQLAlchemy

app=Flask(__name__)
db=SQLAlchemy(app)
bcrypt=Bcrypt(app)


from recommender import routes