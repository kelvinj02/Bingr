import os
import urllib.parse
from flask import Flask
from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from recommender.config import Config

db=SQLAlchemy()
bcrypt=Bcrypt()
login_manager=LoginManager()
login_manager.login_view='users.login'
login_manager.login_message_category='info'
mail = Mail()

def create_app(config_class=Config):
    app=Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)

    from recommender.users.routes import users
    from recommender.reviews.routes import reviews
    from recommender.main.routes import main
    from recommender.details.routes import details
    from recommender.errors.handlers import errors
    from recommender.books.routes import books
    from recommender.movies.routes import movies
    app.register_blueprint(users)
    app.register_blueprint(reviews)
    app.register_blueprint(main)
    app.register_blueprint(details)
    app.register_blueprint(errors)
    app.register_blueprint(books)
    app.register_blueprint(movies)

    @app.template_filter('url_encode_title')
    def url_encode_title(title):
        return urllib.parse.quote(str(title), safe='')

    with app.app_context():
        db.create_all()

    from recommender.ml.recommender import BookRecommender
    csv_path = os.path.join(os.path.dirname(__file__), 'api_clients', 'goodreads_data.csv')
    app.recommender = BookRecommender(csv_path)

    from recommender.ml.movie_recommender import MovieRecommender
    data_path = os.path.join(os.path.dirname(__file__), 'api_clients', 'movies_data.pkl')
    sim_path  = os.path.join(os.path.dirname(__file__), 'api_clients', 'similarity.pkl')
    app.movie_recommender = MovieRecommender(data_path, sim_path)

    return app