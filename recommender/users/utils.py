from flask import url_for, current_app
from flask_mail import Message
from recommender import mail

def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Password Reset Request', sender='noreply@demo.com', recipients=[user.email])
    msg.body = f"""To reset your password, visit to the following link:
{url_for('reset_token', token=token, _external=True)}

If you did not make this request then simply ignore this message and no changes will be made. 
"""
    mail.send(msg)