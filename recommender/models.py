from recommender import db, login_manager
from datetime import datetime
from flask_login import UserMixin

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    __tablename__= 'users'
    id=db.Column(db.Integer, primary_key=True)
    username=db.Column(db.String(20), unique=True, nullable=False)
    email=db.Column(db.String(120), unique=True, nullable=False)
    password=db.Column(db.String(60), nullable=False)
    comments=db.relationship('Comment', backref='author', lazy=True)
    wishlist=db.relationship('WishListItem', backref='author', lazy=True)

    def __repr__(self):
        return f"User('{self.username}', '{self.email}')"    
    
class Comment(db.Model):
    __tablename__= 'comments'
    id=db.Column(db.Integer, primary_key=True)
    user_id=db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content=db.Column(db.Text, nullable=False)
    created_at=db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class WishListItem(db.Model):
    __tablename__= 'wishlist_items'
    id=db.Column(db.Integer, primary_key=True)
    user_id=db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title=db.Column(db.String(60), nullable=False)
    added_at=db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"WishListItem('{self.title}','{self.added_at}')"