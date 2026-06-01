import re
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()
login_manager = LoginManager()


LOGIN_RE = re.compile(r'^[A-Za-z0-9]{5,}$')
PASSWORD_ALLOWED_RE = re.compile(r"^[A-Za-zА-Яа-яЁё0-9~!?@#$%^&*_\-+()\[\]{}><\\/|\"'.,:;]+$")


class Role(db.Model):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=False)


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(120), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(120), nullable=True)
    first_name = db.Column(db.String(120), nullable=False)
    middle_name = db.Column(db.String(120), nullable=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    role = db.relationship('Role', backref='users')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self):
        parts = [self.last_name or '', self.first_name or '', self.middle_name or '']
        return ' '.join(part for part in parts if part).strip() or self.login


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='lab4-secret-key',
        SQLALCHEMY_DATABASE_URI='sqlite:///lab4.db',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        REMEMBER_COOKIE_DURATION=timedelta(days=7),
        SEED_DATA=True,
    )

    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = 'login'
    login_manager.login_message = 'Для доступа к запрашиваемой странице необходимо пройти процедуру аутентификации.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    with app.app_context():
        db.create_all()
        if app.config.get('SEED_DATA', True):
            seed_data()

    register_routes(app)
    return app


def seed_data():
    if Role.query.count() == 0:
        db.session.add_all(
            [
                Role(name='Администратор', description='Полный доступ к управлению пользователями.'),
                Role(name='Пользователь', description='Обычный пользователь системы.'),
            ]
        )
        db.session.commit()

    if User.query.filter_by(login='user').first() is None:
        admin_role = Role.query.filter_by(name='Администратор').first()
        user = User(
            login='user',
            first_name='Тест',
            last_name='Пользователь',
            middle_name='Лабораторный',
            role=admin_role,
        )
        user.set_password('qwerty')
        db.session.add(user)
        db.session.commit()


def is_safe_next_url(target):
    if not target:
        return False
    test_url = urlsplit(target)
    return test_url.scheme == '' and test_url.netloc == ''


def role_name(user):
    return user.role.name if user.role else 'Без роли'


def parse_role_id(raw_role_id):
    if raw_role_id in (None, ''):
        return None, None

    try:
        role_id = int(raw_role_id)
    except ValueError:
        return None, 'Указана некорректная роль.'

    role = db.session.get(Role, role_id)
    if role is None:
        return None, 'Выбранная роль не существует.'

    return role, None


def validate_password(password):
    if not password:
        return 'Поле не может быть пустым.'
    if len(password) < 8:
        return 'Пароль должен содержать не менее 8 символов.'
    if len(password) > 128:
        return 'Пароль должен содержать не более 128 символов.'
    if any(ch.isspace() for ch in password):
        return 'Пароль не должен содержать пробелы.'
    if not re.search(r'[A-ZА-ЯЁ]', password):
        return 'Пароль должен содержать хотя бы одну заглавную букву.'
    if not re.search(r'[a-zа-яё]', password):
        return 'Пароль должен содержать хотя бы одну строчную букву.'
    if not re.search(r'[0-9]', password):
        return 'Пароль должен содержать хотя бы одну цифру.'
    if any(ch.isdigit() and ch not in '0123456789' for ch in password):
        return 'Пароль должен содержать только арабские цифры.'
    if not PASSWORD_ALLOWED_RE.fullmatch(password):
        return 'Пароль содержит недопустимые символы.'
    return None


def validate_create_form(form_data):
    errors = {}

    login = (form_data.get('login') or '').strip()
    password = form_data.get('password') or ''
    last_name = (form_data.get('last_name') or '').strip()
    first_name = (form_data.get('first_name') or '').strip()
    middle_name = (form_data.get('middle_name') or '').strip()
    role, role_error = parse_role_id(form_data.get('role_id'))

    if not login:
        errors['login'] = 'Поле не может быть пустым.'
    elif not LOGIN_RE.fullmatch(login):
        errors['login'] = 'Логин должен состоять из латинских букв и цифр и содержать не менее 5 символов.'
    elif User.query.filter_by(login=login).first() is not None:
        errors['login'] = 'Пользователь с таким логином уже существует.'

    password_error = validate_password(password)
    if password_error:
        errors['password'] = password_error

    if not last_name:
        errors['last_name'] = 'Поле не может быть пустым.'

    if not first_name:
        errors['first_name'] = 'Поле не может быть пустым.'

    if role_error:
        errors['role_id'] = role_error

    cleaned = {
        'login': login,
        'password': password,
        'last_name': last_name,
        'first_name': first_name,
        'middle_name': middle_name,
        'role': role,
    }
    return errors, cleaned


def validate_edit_form(form_data):
    errors = {}

    last_name = (form_data.get('last_name') or '').strip()
    first_name = (form_data.get('first_name') or '').strip()
    middle_name = (form_data.get('middle_name') or '').strip()
    role, role_error = parse_role_id(form_data.get('role_id'))

    if not last_name:
        errors['last_name'] = 'Поле не может быть пустым.'

    if not first_name:
        errors['first_name'] = 'Поле не может быть пустым.'

    if role_error:
        errors['role_id'] = role_error

    cleaned = {
        'last_name': last_name,
        'first_name': first_name,
        'middle_name': middle_name,
        'role': role,
    }
    return errors, cleaned


def register_routes(app):
    @app.route('/')
    def index():
        users = User.query.order_by(User.id.asc()).all()
        return render_template('index.html', title='Пользователи', users=users, role_name=role_name)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'GET':
            return render_template('login.html', title='Вход', form_data={'login': ''})

        login_value = (request.form.get('login') or '').strip()
        password = request.form.get('password') or ''
        remember = request.form.get('remember') == 'on'

        user = User.query.filter_by(login=login_value).first()
        if user is None or not user.check_password(password):
            flash('Неверный логин или пароль.', 'danger')
            return render_template('login.html', title='Вход', form_data={'login': login_value})

        login_user(user, remember=remember)
        flash('Вход выполнен успешно.', 'success')

        next_url = request.args.get('next')
        if is_safe_next_url(next_url):
            return redirect(next_url)

        return redirect(url_for('index'))

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('Вы вышли из системы.', 'info')
        return redirect(url_for('index'))

    @app.route('/users/<int:user_id>')
    def view_user(user_id):
        user = db.session.get(User, user_id)
        if user is None:
            return render_template('404.html', title='Пользователь не найден'), 404
        return render_template('view_user.html', title='Просмотр пользователя', user=user, role_name=role_name)

    @app.route('/users/create', methods=['GET', 'POST'])
    @login_required
    def create_user():
        roles = Role.query.order_by(Role.name.asc()).all()
        form_data = {
            'login': request.form.get('login', ''),
            'password': request.form.get('password', ''),
            'last_name': request.form.get('last_name', ''),
            'first_name': request.form.get('first_name', ''),
            'middle_name': request.form.get('middle_name', ''),
            'role_id': request.form.get('role_id', ''),
        }

        if request.method == 'GET':
            return render_template(
                'create_user.html',
                title='Создание пользователя',
                roles=roles,
                form_data=form_data,
                errors={},
            )

        errors, cleaned = validate_create_form(form_data)
        if errors:
            flash('Исправьте ошибки формы.', 'danger')
            return render_template(
                'create_user.html',
                title='Создание пользователя',
                roles=roles,
                form_data=form_data,
                errors=errors,
            )

        user = User(
            login=cleaned['login'],
            first_name=cleaned['first_name'],
            last_name=cleaned['last_name'],
            middle_name=cleaned['middle_name'] or None,
            role=cleaned['role'],
        )
        user.set_password(cleaned['password'])

        try:
            db.session.add(user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('Не удалось создать пользователя. Возможно, логин уже существует.', 'danger')
            return render_template(
                'create_user.html',
                title='Создание пользователя',
                roles=roles,
                form_data=form_data,
                errors={'login': 'Пользователь с таким логином уже существует.'},
            )

        flash('Пользователь успешно создан.', 'success')
        return redirect(url_for('index'))

    @app.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_user(user_id):
        user = db.session.get(User, user_id)
        if user is None:
            return render_template('404.html', title='Пользователь не найден'), 404

        roles = Role.query.order_by(Role.name.asc()).all()

        if request.method == 'GET':
            form_data = {
                'last_name': user.last_name or '',
                'first_name': user.first_name or '',
                'middle_name': user.middle_name or '',
                'role_id': str(user.role_id) if user.role_id else '',
            }
            return render_template(
                'edit_user.html',
                title='Редактирование пользователя',
                user=user,
                roles=roles,
                form_data=form_data,
                errors={},
            )

        form_data = {
            'last_name': request.form.get('last_name', ''),
            'first_name': request.form.get('first_name', ''),
            'middle_name': request.form.get('middle_name', ''),
            'role_id': request.form.get('role_id', ''),
        }

        errors, cleaned = validate_edit_form(form_data)
        if errors:
            flash('Исправьте ошибки формы.', 'danger')
            return render_template(
                'edit_user.html',
                title='Редактирование пользователя',
                user=user,
                roles=roles,
                form_data=form_data,
                errors=errors,
            )

        user.last_name = cleaned['last_name']
        user.first_name = cleaned['first_name']
        user.middle_name = cleaned['middle_name'] or None
        user.role = cleaned['role']

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('Не удалось сохранить изменения пользователя.', 'danger')
            return render_template(
                'edit_user.html',
                title='Редактирование пользователя',
                user=user,
                roles=roles,
                form_data=form_data,
                errors={},
            )

        flash('Пользователь успешно обновлён.', 'success')
        return redirect(url_for('index'))

    @app.route('/users/<int:user_id>/delete', methods=['POST'])
    @login_required
    def delete_user(user_id):
        user = db.session.get(User, user_id)
        if user is None:
            flash('Пользователь не найден.', 'danger')
            return redirect(url_for('index'))

        try:
            db.session.delete(user)
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash('Не удалось удалить пользователя.', 'danger')
            return redirect(url_for('index'))

        flash('Пользователь успешно удалён.', 'success')
        return redirect(url_for('index'))

    @app.route('/change-password', methods=['GET', 'POST'])
    @login_required
    def change_password():
        form_data = {
            'old_password': request.form.get('old_password', ''),
            'new_password': request.form.get('new_password', ''),
            'new_password_confirm': request.form.get('new_password_confirm', ''),
        }

        if request.method == 'GET':
            return render_template(
                'change_password.html',
                title='Изменить пароль',
                errors={},
                form_data={'old_password': '', 'new_password': '', 'new_password_confirm': ''},
            )

        errors = {}
        if not current_user.check_password(form_data['old_password']):
            errors['old_password'] = 'Старый пароль введён неверно.'

        new_password_error = validate_password(form_data['new_password'])
        if new_password_error:
            errors['new_password'] = new_password_error

        if form_data['new_password'] != form_data['new_password_confirm']:
            errors['new_password_confirm'] = 'Новые пароли не совпадают.'

        if errors:
            flash('Исправьте ошибки формы.', 'danger')
            return render_template(
                'change_password.html',
                title='Изменить пароль',
                errors=errors,
                form_data=form_data,
            )

        current_user.set_password(form_data['new_password'])
        db.session.commit()
        flash('Пароль успешно изменён.', 'success')
        return redirect(url_for('index'))


app = create_app()
application = app


if __name__ == '__main__':
    app.run(debug=True)
