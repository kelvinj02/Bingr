import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    TMDB_API_KEY = os.environ.get('TMDB_API_KEY')
    BOOKS_API_KEY = os.environ.get('BOOKS_API_KEY')
    DEBUG = os.environ.get('DEBUG', 'False') == 'True'
    SQLALCHEMY_TRACK_MODIFICATIONS = False