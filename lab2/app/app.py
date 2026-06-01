import random
import re
from functools import lru_cache

from faker import Faker
from flask import Flask, abort, make_response, render_template, request

fake = Faker()

app = Flask(__name__)
application = app

images_ids = [
    '7d4e9175-95ea-4c5f-8be5-92a6b708bb3c',
    '2d2ab7df-cdbc-48a8-a936-35bba702def5',
    '6e12f3de-d5fd-4ebb-855b-8cbc485278b7',
    'afc2cfe7-5cac-4b80-9b9a-d5c65ef0c728',
    'cab5b7f2-774e-4884-a200-0c0180fa777f',
]

TOGGLE_COOKIE_NAME = 'lab2_mode'
TOGGLE_COOKIE_VALUE = 'enabled'
ALLOWED_PHONE_CHARS_RE = re.compile(r'^[\d\s().+\-]*$')
INVALID_COUNT_MESSAGE = 'Недопустимый ввод. Неверное количество цифр.'
INVALID_CHARS_MESSAGE = 'Недопустимый ввод. В номере телефона встречаются недопустимые символы.'


def generate_comments(replies=True):
    comments = []
    for _ in range(random.randint(1, 3)):
        comment = {'author': fake.name(), 'text': fake.text()}
        if replies:
            comment['replies'] = generate_comments(replies=False)
        comments.append(comment)
    return comments


def generate_post(i):
    return {
        'title': 'Заголовок поста',
        'text': fake.paragraph(nb_sentences=100),
        'author': fake.name(),
        'date': fake.date_time_between(start_date='-2y', end_date='now'),
        'image_id': f'{images_ids[i]}.jpg',
        'comments': generate_comments(),
    }


@lru_cache
def posts_list():
    return sorted([generate_post(i) for i in range(5)], key=lambda p: p['date'], reverse=True)


@app.route('/')
def index():
    return render_template('index.html', title='ЛР1 + ЛР2 Flask')


@app.route('/posts')
def posts():
    return render_template('posts.html', title='Посты', posts=posts_list())


@app.route('/posts/<int:index>')
def post(index):
    posts_data = posts_list()
    if index < 0 or index >= len(posts_data):
        abort(404)

    p = posts_data[index]
    return render_template('post.html', title=p['title'], post=p)


@app.route('/about')
def about():
    return render_template('about.html', title='Об авторе')


@app.route('/url-params')
def url_params_page():
    return render_template('url_params.html', title='Параметры URL', params=request.args.lists())


@app.route('/headers')
def headers_page():
    return render_template('headers.html', title='Заголовки запроса', headers=request.headers.items())


@app.route('/cookies')
def cookies_page():
    current_value = request.cookies.get(TOGGLE_COOKIE_NAME)
    response = make_response(
        render_template(
            'cookies.html',
            title='Cookie',
            cookie_name=TOGGLE_COOKIE_NAME,
            cookie_value=current_value,
            all_cookies=request.cookies.items(),
            action='set' if current_value is None else 'delete',
        )
    )

    if current_value is None:
        response.set_cookie(TOGGLE_COOKIE_NAME, TOGGLE_COOKIE_VALUE)
    else:
        response.delete_cookie(TOGGLE_COOKIE_NAME)

    return response


@app.route('/form-params', methods=['GET', 'POST'])
def form_params_page():
    submitted = request.form.items()
    return render_template('form_params.html', title='Параметры формы', submitted=submitted)


def get_phone_error(phone_raw):
    stripped = phone_raw.strip()

    if not ALLOWED_PHONE_CHARS_RE.fullmatch(phone_raw):
        return INVALID_CHARS_MESSAGE

    digits = ''.join(ch for ch in phone_raw if ch.isdigit())
    required_count = 11 if stripped.startswith('+7') or stripped.startswith('8') else 10

    if len(digits) != required_count:
        return INVALID_COUNT_MESSAGE

    return None


def format_phone_number(phone_raw):
    digits = ''.join(ch for ch in phone_raw if ch.isdigit())

    if len(digits) == 10:
        digits = '8' + digits
    elif len(digits) == 11 and digits.startswith('7'):
        digits = '8' + digits[1:]

    return f'{digits[0]}-{digits[1:4]}-{digits[4:7]}-{digits[7:9]}-{digits[9:11]}'


@app.route('/phone', methods=['GET', 'POST'])
def phone_page():
    phone_raw = ''
    error_message = None
    formatted_phone = None

    if request.method == 'POST':
        phone_raw = request.form.get('phone', '')
        error_message = get_phone_error(phone_raw)

        if error_message is None:
            formatted_phone = format_phone_number(phone_raw)

    return render_template(
        'phone.html',
        title='Проверка телефона',
        phone_raw=phone_raw,
        error_message=error_message,
        formatted_phone=formatted_phone,
    )
