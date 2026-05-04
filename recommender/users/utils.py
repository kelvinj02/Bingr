import logging
import threading
from flask import url_for, current_app
from flask_mail import Message
from recommender import mail

logger = logging.getLogger(__name__)


def _send_async(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            logger.error("Failed to send email to %s: %s", msg.recipients, e)


def send_reset_email(user):
    token = user.get_reset_token()
    reset_url = url_for('users.reset_token', token=token, _external=True)
    msg = Message(
        'Password Reset Request',
        sender=current_app.config['MAIL_USERNAME'],
        recipients=[user.email],
    )
    msg.body = f"""To reset your password, visit the following link:
{reset_url}

If you did not make this request then simply ignore this message and no changes will be made.
"""
    app = current_app._get_current_object()
    thread = threading.Thread(target=_send_async, args=(app, msg), daemon=True)
    thread.start()