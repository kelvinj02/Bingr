from recommender import db, login_manager
from datetime import datetime
from flask_login import UserMixin
from itsdangerous import URLSafeTimedSerializer as Serializer
from flask import current_app

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    __tablename__= 'users'
    id=db.Column(db.Integer, primary_key=True)
    username=db.Column(db.String(20), unique=True, nullable=False)
    email=db.Column(db.String(120), unique=True, nullable=False)
    password=db.Column(db.String(60), nullable=False)
    #comments=db.relationship('Comment', backref='author', lazy=True)
    #wishlist=db.relationship('WishListItem', backref='author', lazy=True)

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

    def __repr__(self):
        return f"User('{self.username}', '{self.email}')"    
    
# class Comment(db.Model):
#     __tablename__= 'comments'
#     id=db.Column(db.Integer, primary_key=True)
#     user_id=db.Column(db.Integer, db.ForeignKey('id'), nullable=False)
#     content=db.Column(db.Text, nullable=False)
#     created_at=db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

# class WishListItem(db.Model):
#     __tablename__= 'wishlist_items'
#     id=db.Column(db.Integer, primary_key=True)
#     user_id=db.Column(db.Integer, db.ForeignKey('id'), nullable=False)
#     title=db.Column(db.String(60), nullable=False)
#     added_at=db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

#     def __repr__(self):
#         return f"WishListItem('{self.title}','{self.added_at}')"