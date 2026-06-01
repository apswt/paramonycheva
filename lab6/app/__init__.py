import hashlib
import os
import uuid
import shutil

from flask import Flask
from flask_migrate import Migrate
from sqlalchemy.exc import SQLAlchemyError

from app.models import db, Category, User, Course, Image
from app.auth import bp as auth_bp, init_login_manager
from app.courses import bp as courses_bp
from app.routes import bp as main_bp

def handle_sqlalchemy_error(err):
    error_msg = ('Возникла ошибка при подключении к базе данных. '
                 'Повторите попытку позже.')
    return f'{error_msg} (Подробнее: {err})', 500


def _seed_defaults(app):
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    db.create_all()

    if db.session.execute(db.select(Category)).first() is None:
        db.session.add_all(
            [
                Category(name='Программирование'),
                Category(name='Математика'),
                Category(name='Языкознание'),
            ]
        )
        db.session.commit()

    user = db.session.execute(db.select(User).filter_by(login='user')).scalar()
    if user is None:
        user = User(first_name='Иван', last_name='Иванов', middle_name='Иванович', login='user')
        user.set_password('qwerty')
        db.session.add(user)
        db.session.commit()

    course_exists = db.session.execute(db.select(Course)).first() is not None
    if course_exists:
        return

    category = db.session.execute(db.select(Category)).scalar()
    static_img = os.path.join(app.root_path, 'static', 'images', 'default-profile-picture-300x300.jpeg')
    with open(static_img, 'rb') as image_file:
        content = image_file.read()
        md5_hash = hashlib.md5(content).hexdigest()

    image = db.session.execute(db.select(Image).filter_by(md5_hash=md5_hash)).scalar()
    if image is None:
        image = Image(
            id=str(uuid.uuid4()),
            file_name='demo-course.jpeg',
            mime_type='image/jpeg',
            md5_hash=md5_hash,
        )
        _, ext = os.path.splitext(image.file_name)
        shutil.copyfile(static_img, os.path.join(app.config['UPLOAD_FOLDER'], f'{image.id}{ext}'))
        db.session.add(image)
        db.session.commit()

    demo_course = Course(
        name='Введение в Python',
        short_desc='Базовый курс по Python: синтаксис, функции, структуры данных.',
        full_desc='На курсе разберем основы Python и практические примеры для старта в программировании.',
        category_id=category.id,
        author_id=user.id,
        background_image_id=image.id,
    )
    db.session.add(demo_course)
    db.session.commit()


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_pyfile('config.py')

    if test_config:
        app.config.from_mapping(test_config)

    db.init_app(app)
    Migrate(app, db)

    init_login_manager(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(courses_bp)
    app.register_blueprint(main_bp)
    app.errorhandler(SQLAlchemyError)(handle_sqlalchemy_error)

    if app.config.get('AUTO_SETUP', True):
        with app.app_context():
            _seed_defaults(app)

    return app
