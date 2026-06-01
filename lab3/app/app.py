from datetime import timedelta
from urllib.parse import urlsplit

from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)

app = Flask(__name__)
application = app
app.config['SECRET_KEY'] = 'lab3-secret-key'
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=7)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Для доступа к запрашиваемой странице необходимо пройти процедуру аутентификации.'
login_manager.login_message_category = 'warning'


class User(UserMixin):
    def __init__(self, user_id, username, password):
        self.id = user_id
        self.username = username
        self.password = password


TEST_USER = User(user_id='1', username='user', password='qwerty')
USERS = {TEST_USER.id: TEST_USER}
USERS_BY_LOGIN = {TEST_USER.username: TEST_USER}


@login_manager.user_loader
def load_user(user_id):
    return USERS.get(user_id)


def is_safe_next_url(target):
    if not target:
        return False

    test_url = urlsplit(target)
    return test_url.scheme == '' and test_url.netloc == ''


@app.route('/')
def index():
    return render_template('index.html', title='Лабораторная работа №3')


@app.route('/visit-counter')
def visit_counter():
    visits = session.get('visit_counter', 0) + 1
    session['visit_counter'] = visits
    return render_template('visit_counter.html', title='Счётчик посещений', visits=visits)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html', title='Вход', username='')

    username = request.form.get('username', '')
    password = request.form.get('password', '')
    remember = request.form.get('remember') == 'on'

    user = USERS_BY_LOGIN.get(username)
    if user is None or user.password != password:
        flash('Неверный логин или пароль.', 'danger')
        return render_template('login.html', title='Вход', username=username), 401

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


@app.route('/secret')
@login_required
def secret_page():
    return render_template('secret.html', title='Секретная страница')


if __name__ == '__main__':
    app.run(debug=True)
