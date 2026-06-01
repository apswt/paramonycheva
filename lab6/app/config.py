import os

SECRET_KEY = os.environ.get('SECRET_KEY', 'secret-key')

SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///project.db')
# SQLALCHEMY_DATABASE_URI = 'mysql+mysqlconnector://user:password@std-mysql.ist.mospolytech.ru/db_name'
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ECHO = False
AUTO_SETUP = os.environ.get('AUTO_SETUP', '1') == '1'

UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 
    '..',
    'media', 
    'images'
)
