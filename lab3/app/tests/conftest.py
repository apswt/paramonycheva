from contextlib import contextmanager

import pytest
from flask import template_rendered
from flask_login import FlaskLoginClient

from app import TEST_USER, app as application


@pytest.fixture
def app():
    application.config.update(TESTING=True)
    application.test_client_class = FlaskLoginClient
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(app):
    return app.test_client(user=TEST_USER)


@pytest.fixture
@contextmanager
def captured_templates(app):
    recorded = []

    def record(sender, template, context, **extra):
        recorded.append((template, context))

    template_rendered.connect(record, app)
    try:
        yield recorded
    finally:
        template_rendered.disconnect(record, app)
