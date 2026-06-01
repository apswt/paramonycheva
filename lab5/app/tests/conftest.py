import pytest

from app import User, create_app, db, seed_data


@pytest.fixture
def app(tmp_path):
    db_path = tmp_path / 'lab5_test.db'
    application = create_app(
        {
            'TESTING': True,
            'SECRET_KEY': 'test-secret-key',
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
            'SEED_DATA': False,
            'LOG_VISITS': True,
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
def user_ids(app):
    with app.app_context():
        admin = User.query.filter_by(login='admin').first()
        regular = User.query.filter_by(login='user01').first()
        return {'admin': admin.id, 'regular': regular.id}
