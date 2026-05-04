from recommender import db, login_manager
from datetime import datetime
from flask_login import UserMixin
from itsdangerous import URLSafeTimedSerializer as Serializer
from flask import current_app
from sqlalchemy import UniqueConstraint, CheckConstraint

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    __tablename__= 'users'
    id=db.Column(db.Integer, primary_key=True)
    username=db.Column(db.String(20), unique=True, nullable=False)
    email=db.Column(db.String(120), unique=True, nullable=False)
    password=db.Column(db.String(60), nullable=False)
    created_at=db.Column(db.DateTime, nullable=True, default=datetime.utcnow)
    comments=db.relationship('Comment', backref='author', lazy=True)
    wishlist=db.relationship('WishListItem', backref='author', lazy=True)

    #create a signer using a secret key with a 10 mins expiry
    #and return a token string 
    def get_reset_token(self, expires_sec=600):
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id}, salt='reset-password')
    
    @staticmethod
    def verify_reset_token(token, expires_sec=600):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token, salt='reset-password', max_age=expires_sec)['user_id']
        except:
            return None
        return User.query.get(user_id)

    preferences = db.relationship('UserPreference', backref='user', lazy=True, cascade='all, delete-orphan')
    books = db.relationship('UserBook', backref='user', lazy=True, cascade='all, delete-orphan')
    movies = db.relationship('UserMovie', backref='user', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"User('{self.username}', '{self.email}', '{self.created_at}')"


class UserPreference(db.Model):
    __tablename__ = 'user_preferences'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    pref_type = db.Column(db.String(10), nullable=False)
    value = db.Column(db.String(100), nullable=False)

    __table_args__ = (
        UniqueConstraint('user_id', 'pref_type', 'value', name='uq_user_pref'),
        CheckConstraint("pref_type IN ('genre', 'author')", name='ck_pref_type'),
    )

    def __repr__(self):
        return f"UserPreference('{self.pref_type}', '{self.value}')"


class UserBook(db.Model):
    __tablename__ = 'user_books'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    book_title = db.Column(db.String(300), nullable=False)
    status = db.Column(db.String(10), nullable=False)
    rating = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('user_id', 'book_title', name='uq_user_book'),
        CheckConstraint("status IN ('read', 'saved')", name='ck_book_status'),
        CheckConstraint('rating IS NULL OR (rating >= 1 AND rating <= 5)', name='ck_book_rating'),
    )

    def __repr__(self):
        return f"UserBook('{self.book_title}', '{self.status}', rating={self.rating})"


class UserMovie(db.Model):
    __tablename__ = 'user_movies'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    movie_title = db.Column(db.String(300), nullable=False)
    status = db.Column(db.String(10), nullable=False)
    rating = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('user_id', 'movie_title', name='uq_user_movie'),
        CheckConstraint("status IN ('watched', 'saved')", name='ck_movie_status'),
        CheckConstraint('rating IS NULL OR (rating >= 1 AND rating <= 5)', name='ck_movie_rating'),
    )

    def __repr__(self):
        return f"UserMovie('{self.movie_title}', '{self.status}', rating={self.rating})"


class Comment(db.Model):
    __tablename__= 'comments'
    id=db.Column(db.Integer, primary_key=True)
    user_id=db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    item_type=db.Column(db.String(10), nullable=False)   # 'movie' or 'book'
    item_id = db.Column(db.String(50), nullable=False)   # external API ID
    review_score=db.Column(db.Float, nullable=False)
    content=db.Column(db.Text, nullable=False)
    created_at=db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"Comment('{self.item_type}', '{self.item_id}', score={self.review_score})"

class SearchHistory(db.Model):
    __tablename__ = 'search_history'
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    search_query = db.Column(db.String(200), nullable=False)
    result_type  = db.Column(db.String(10), nullable=True)  # 'book', 'movie', or None for 'all'
    searched_at  = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"SearchHistory(user={self.user_id}, '{self.query}')"


class WishListItem(db.Model):
    __tablename__= 'wishlist_items'
    id=db.Column(db.Integer, primary_key=True)
    user_id=db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    item_type =db.Column(db.String(10), nullable=False)
    item_id =db.Column(db.String(50), nullable=False)
    title=db.Column(db.String(60), nullable=False)
    added_at=db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"WishListItem('{self.title}','{self.added_at}')"