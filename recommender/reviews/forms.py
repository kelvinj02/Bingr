from flask_wtf import FlaskForm
from wtforms import SubmitField, FloatField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange

#Comment Form
class CommentForm(FlaskForm):
    review_score = FloatField("Rating", validators=[DataRequired(), NumberRange(min=0.5, max=5)])
    body = TextAreaField("Comment Content", validators=[DataRequired(), Length(min=1, max=200)])
    submit = SubmitField("Post")