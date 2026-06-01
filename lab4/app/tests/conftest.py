import pytest

from app import User, create_app, db, seed_data


@pytest.fixture
def app(tmp_path):
    db_path = tmp_path / 'lab4_test.db'
    application = create_app(
        {
            'TESTING': True,
            'SECRET_KEY': 'test-secret-key',
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
            'SEED_DATA': False,
        }
    )

    with application.app_context():
        db.drop_all()
        db.create_all()
        seed_data()

    yield application

    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def default_user_id(app):
    with app.app_context():
        user = User.query.filter_by(login='user').first()
        return user.id
