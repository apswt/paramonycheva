import re
from datetime import datetime, timedelta
from functools import wraps
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


RIGHT_CREATE_USER = 'create_user'
RIGHT_EDIT_USER = 'edit_user'
RIGHT_VIEW_USER = 'view_user'
RIGHT_DELETE_USER = 'delete_user'
RIGHT_VIEW_LOGS = 'view_logs'
RIGHT_VIEW_LOG_REPORTS = 'view_log_reports'
RIGHT_CHANGE_PASSWORD = 'change_password'

ROLE_ADMIN = 'Администратор'
ROLE_USER = 'Пользователь'

ROLE_RIGHTS = {
    ROLE_ADMIN: {
        RIGHT_CREATE_USER,
        RIGHT_EDIT_USER,
        RIGHT_VIEW_USER,
        RIGHT_DELETE_USER,
        RIGHT_VIEW_LOGS,
        RIGHT_VIEW_LOG_REPORTS,
        RIGHT_CHANGE_PASSWORD,
    },
    ROLE_USER: {
        RIGHT_EDIT_USER,
        RIGHT_VIEW_USER,
        RIGHT_VIEW_LOGS,
        RIGHT_CHANGE_PASSWORD,
    },
}

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


class VisitLog(db.Model):
    __tablename__ = 'visit_logs'

    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship('User', backref='visit_logs')


def role_name(user):
    return user.role.name if user.role else 'Без роли'


def is_admin(user):
    return bool(user.is_authenticated and user.role and user.role.name == ROLE_ADMIN)


def is_regular_user(user):
    return bool(user.is_authenticated and user.role and user.role.name == ROLE_USER)


def get_user_rights(user):
    if not user.is_authenticated or user.role is None:
        return set()
    return ROLE_RIGHTS.get(user.role.name, set())


def has_right(user, right_name):
    return right_name in get_user_rights(user)


def check_rights(right_name):
    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            if not has_right(current_user, right_name):
                flash('У вас недостаточно прав для доступа к данной странице.', 'danger')
                return redirect(url_for('index'))
            return func(*args, **kwargs)

        return wrapped

    return decorator


def can_view_user(viewer, target):
    if not has_right(viewer, RIGHT_VIEW_USER):
        return False
    if is_admin(viewer):
        return True
    return viewer.id == target.id


def can_edit_user(viewer, target):
    if not has_right(viewer, RIGHT_EDIT_USER):
        return False
    if is_admin(viewer):
        return True
    return viewer.id == target.id


def can_delete_user(viewer, target):
    return has_right(viewer, RIGHT_DELETE_USER) and is_admin(viewer)


def can_create_user(viewer):
    return has_right(viewer, RIGHT_CREATE_USER)


def can_view_log_reports(viewer):
    return has_right(viewer, RIGHT_VIEW_LOG_REPORTS)


def can_view_logs(viewer):
    return has_right(viewer, RIGHT_VIEW_LOGS)


def is_safe_next_url(target):
    if not target:
        return False
    test_url = urlsplit(target)
    return test_url.scheme == '' and test_url.netloc == ''


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

    login_value = (form_data.get('login') or '').strip()
    password = form_data.get('password') or ''
    last_name = (form_data.get('last_name') or '').strip()
    first_name = (form_data.get('first_name') or '').strip()
    middle_name = (form_data.get('middle_name') or '').strip()
    role, role_error = parse_role_id(form_data.get('role_id'))

    if not login_value:
        errors['login'] = 'Поле не может быть пустым.'
    elif not LOGIN_RE.fullmatch(login_value):
        errors['login'] = 'Логин должен состоять из латинских букв и цифр и содержать не менее 5 символов.'
    elif User.query.filter_by(login=login_value).first() is not None:
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
        'login': login_value,
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

    if not last_name:
        errors['last_name'] = 'Поле не может быть пустым.'

    if not first_name:
        errors['first_name'] = 'Поле не может быть пустым.'

    cleaned = {
        'last_name': last_name,
        'first_name': first_name,
        'middle_name': middle_name,
    }
    return errors, cleaned


def seed_data():
    if Role.query.count() == 0:
        db.session.add_all(
            [
                Role(name=ROLE_ADMIN, description='Полный доступ к управлению пользователями и отчётами.'),
                Role(name=ROLE_USER, description='Ограниченный доступ: собственный профиль и личный журнал посещений.'),
            ]
        )
        db.session.commit()

    admin_role = Role.query.filter_by(name=ROLE_ADMIN).first()
    user_role = Role.query.filter_by(name=ROLE_USER).first()

    if User.query.filter_by(login='admin').first() is None:
        admin = User(
            login='admin',
            first_name='Системный',
            last_name='Администратор',
            middle_name='Главный',
            role=admin_role,
        )
        admin.set_password('Admin123!')
        db.session.add(admin)

    if User.query.filter_by(login='user01').first() is None:
        regular = User(
            login='user01',
            first_name='Обычный',
            last_name='Пользователь',
            middle_name='Тестовый',
            role=user_role,
        )
        regular.set_password('User123!')
        db.session.add(regular)

    db.session.commit()


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='lab5-secret-key',
        SQLALCHEMY_DATABASE_URI='sqlite:///lab5.db',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        REMEMBER_COOKIE_DURATION=timedelta(days=7),
        SEED_DATA=True,
        LOG_VISITS=True,
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

    @app.before_request
    def log_visit():
        if not app.config.get('LOG_VISITS', True):
            return None

        endpoint = request.endpoint or ''
        if endpoint == 'static' or endpoint.endswith('.static'):
            return None
        if request.path.startswith('/static/') or request.path == '/favicon.ico':
            return None

        user_id = current_user.id if current_user.is_authenticated else None
        log = VisitLog(path=request.path[:100], user_id=user_id)
        db.session.add(log)
        db.session.commit()
        return None

    @app.context_processor
    def inject_permissions():
        return {
            'role_name': role_name,
            'can_view_user': can_view_user,
            'can_edit_user': can_edit_user,
            'can_delete_user': can_delete_user,
            'can_create_user': can_create_user,
            'can_view_logs': can_view_logs,
            'can_view_log_reports': can_view_log_reports,
        }

    register_routes(app)

    with app.app_context():
        db.create_all()
        if app.config.get('SEED_DATA', True):
            seed_data()

    from reports import reports_bp

    app.register_blueprint(reports_bp)
    return app


def register_routes(app):
    @app.route('/')
    def index():
        users = User.query.order_by(User.id.asc()).all()
        return render_template('index.html', title='Пользователи', users=users)

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
    @login_required
    @check_rights(RIGHT_VIEW_USER)
    def view_user(user_id):
        user = db.session.get(User, user_id)
        if user is None:
            return render_template('404.html', title='Пользователь не найден'), 404

        if not can_view_user(current_user, user):
            flash('У вас недостаточно прав для доступа к данной странице.', 'danger')
            return redirect(url_for('index'))

        return render_template('view_user.html', title='Просмотр пользователя', user=user)

    @app.route('/users/create', methods=['GET', 'POST'])
    @login_required
    @check_rights(RIGHT_CREATE_USER)
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
    @check_rights(RIGHT_EDIT_USER)
    def edit_user(user_id):
        user = db.session.get(User, user_id)
        if user is None:
            return render_template('404.html', title='Пользователь не найден'), 404

        if not can_edit_user(current_user, user):
            flash('У вас недостаточно прав для доступа к данной странице.', 'danger')
            return redirect(url_for('index'))

        roles = Role.query.order_by(Role.name.asc()).all()
        role_locked = is_regular_user(current_user)

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
                role_locked=role_locked,
            )

        form_data = {
            'last_name': request.form.get('last_name', ''),
            'first_name': request.form.get('first_name', ''),
            'middle_name': request.form.get('middle_name', ''),
            'role_id': request.form.get('role_id', ''),
        }

        errors, cleaned = validate_edit_form(form_data)

        selected_role = user.role
        if not role_locked:
            selected_role, role_error = parse_role_id(form_data.get('role_id'))
            if role_error:
                errors['role_id'] = role_error

        if errors:
            flash('Исправьте ошибки формы.', 'danger')
            return render_template(
                'edit_user.html',
                title='Редактирование пользователя',
                user=user,
                roles=roles,
                form_data=form_data,
                errors=errors,
                role_locked=role_locked,
            )

        user.last_name = cleaned['last_name']
        user.first_name = cleaned['first_name']
        user.middle_name = cleaned['middle_name'] or None
        if not role_locked:
            user.role = selected_role

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
                role_locked=role_locked,
            )

        flash('Пользователь успешно обновлён.', 'success')
        return redirect(url_for('index'))

    @app.route('/users/<int:user_id>/delete', methods=['POST'])
    @login_required
    @check_rights(RIGHT_DELETE_USER)
    def delete_user(user_id):
        user = db.session.get(User, user_id)
        if user is None:
            flash('Пользователь не найден.', 'danger')
            return redirect(url_for('index'))

        if not can_delete_user(current_user, user):
            flash('У вас недостаточно прав для доступа к данной странице.', 'danger')
            return redirect(url_for('index'))

        try:
            VisitLog.query.filter_by(user_id=user.id).update({'user_id': None})
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
    @check_rights(RIGHT_CHANGE_PASSWORD)
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
