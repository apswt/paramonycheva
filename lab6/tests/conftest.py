from pathlib import Path

import pytest

from app import create_app
from app.models import db, Category, Course, Image, User


@pytest.fixture
def app(tmp_path):
    db_path = tmp_path / 'lab6_test.db'
    upload_dir = tmp_path / 'images'
    upload_dir.mkdir(parents=True, exist_ok=True)

    application = create_app(
        {
            'TESTING': True,
            'SECRET_KEY': 'test-secret-key',
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            'AUTO_SETUP': False,
            'UPLOAD_FOLDER': str(upload_dir),
        }
    )

    with application.app_context():
        db.drop_all()
        db.create_all()

        category = Category(name='Программирование')
        db.session.add(category)
        db.session.flush()

        users = []
        for i in range(12):
            login = 'user' if i == 0 else f'reviewer{i}'
            user = User(
                first_name=f'Имя{i}',
                last_name=f'Фамилия{i}',
                middle_name=f'Отчество{i}',
                login=login,
            )
            user.set_password('qwerty')
            users.append(user)

        author = User(
            first_name='Автор',
            last_name='Курса',
            middle_name='Петрович',
            login='author',
        )
        author.set_password('qwerty')
        users.append(author)

        db.session.add_all(users)
        db.session.flush()

        image = Image(
            id='img-course',
            file_name='course.jpg',
            mime_type='image/jpeg',
            md5_hash='md5-course-image',
        )
        db.session.add(image)
        db.session.flush()

        Path(upload_dir / 'img-course.jpg').write_bytes(b'fake-image')

        course = Course(
            name='Тестовый курс',
            short_desc='Краткое описание тестового курса',
            full_desc='Полное описание тестового курса',
            category_id=category.id,
            author_id=author.id,
            background_image_id=image.id,
        )
        db.session.add(course)
        db.session.commit()

    yield application

    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def seed_data(app):
    from app.models import Course, Review, User

    with app.app_context():
        course = db.session.execute(db.select(Course)).scalar()
        users = db.session.execute(
            db.select(User).where(User.login.like('reviewer%')).order_by(User.id.asc())
        ).scalars().all()
        base_user = db.session.execute(db.select(User).where(User.login == 'user')).scalar()
        return {
            'course_id': course.id,
            'reviewer_ids': [base_user.id] + [user.id for user in users],
            'base_user_id': base_user.id,
        }
