from app import Role, User, db


def login(client, remember=False, next_url=None, password='qwerty'):
    data = {'login': 'user', 'password': password}
    if remember:
        data['remember'] = 'on'

    url = '/login'
    if next_url:
        url += f'?next={next_url}'

    return client.post(url, data=data, follow_redirects=True)


def create_user_payload(login_value='newuser1', password='StrongPass1!'):
    return {
        'login': login_value,
        'password': password,
        'last_name': 'Иванов',
        'first_name': 'Иван',
        'middle_name': 'Иванович',
        'role_id': '',
    }


def test_index_displays_users_table(client):
    response = client.get('/')

    assert response.status_code == 200
    assert 'Список пользователей' in response.text
    assert 'Пользователь Тест Лабораторный' in response.text


def test_index_hides_management_for_anonymous(client):
    response = client.get('/')

    assert 'Создание пользователя' not in response.text
    assert 'Редактирование' not in response.text
    assert 'Удаление' not in response.text


def test_index_shows_management_for_authenticated(client):
    login(client)
    response = client.get('/')

    assert 'Создание пользователя' in response.text
    assert 'Редактирование' in response.text
    assert 'Удаление' in response.text


def test_login_success_redirects_to_index(client):
    response = login(client)

    assert response.request.path == '/'
    assert 'Вход выполнен успешно.' in response.text


def test_login_failure_shows_error(client):
    response = client.post('/login', data={'login': 'user', 'password': 'wrong'}, follow_redirects=True)

    assert response.request.path == '/login'
    assert 'Неверный логин или пароль.' in response.text


def test_view_user_is_public(client, default_user_id):
    response = client.get(f'/users/{default_user_id}')

    assert response.status_code == 200
    assert 'Просмотр пользователя' in response.text
    assert 'user' in response.text


def test_create_user_requires_auth(client):
    response = client.get('/users/create', follow_redirects=True)

    assert response.request.path == '/login'
    assert 'Для доступа к запрашиваемой странице необходимо пройти процедуру аутентификации.' in response.text


def test_create_user_success(client, app):
    login(client)
    response = client.post('/users/create', data=create_user_payload(), follow_redirects=True)

    assert response.request.path == '/'
    assert 'Пользователь успешно создан.' in response.text

    with app.app_context():
        user = User.query.filter_by(login='newuser1').first()
        assert user is not None
        assert user.created_at is not None


def test_create_user_can_have_empty_role(client, app):
    login(client)
    payload = create_user_payload(login_value='norole1')
    payload['role_id'] = ''
    client.post('/users/create', data=payload, follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(login='norole1').first()
        assert user is not None
        assert user.role is None


def test_create_user_validation_empty_required_fields(client):
    login(client)
    response = client.post(
        '/users/create',
        data={'login': '', 'password': '', 'last_name': '', 'first_name': '', 'middle_name': '', 'role_id': ''},
        follow_redirects=True,
    )

    assert 'Исправьте ошибки формы.' in response.text
    assert response.text.count('is-invalid') >= 4
    assert 'Поле не может быть пустым.' in response.text


def test_create_user_validation_login_format(client):
    login(client)
    payload = create_user_payload(login_value='ab!')
    response = client.post('/users/create', data=payload, follow_redirects=True)

    assert 'Логин должен состоять из латинских букв и цифр и содержать не менее 5 символов.' in response.text


def test_create_user_validation_password_rules(client):
    login(client)
    payload = create_user_payload(login_value='login5', password='short1A')
    response = client.post('/users/create', data=payload, follow_redirects=True)

    assert 'Пароль должен содержать не менее 8 символов.' in response.text


def test_create_user_duplicate_login_error(client):
    login(client)
    first_payload = create_user_payload(login_value='dupuser1')
    client.post('/users/create', data=first_payload, follow_redirects=True)

    payload = create_user_payload(login_value='dupuser1')
    response = client.post('/users/create', data=payload, follow_redirects=True)

    assert 'Пользователь с таким логином уже существует.' in response.text


def test_edit_user_requires_auth(client, default_user_id):
    response = client.get(f'/users/{default_user_id}/edit', follow_redirects=True)

    assert response.request.path == '/login'


def test_edit_page_uses_macro_without_login_password_fields(client, default_user_id):
    login(client)
    response = client.get(f'/users/{default_user_id}/edit')

    assert response.status_code == 200
    assert 'name="login"' not in response.text
    assert 'name="password"' not in response.text


def test_edit_user_success(client, app, default_user_id):
    login(client)
    payload = {'last_name': 'Смирнов', 'first_name': 'Петр', 'middle_name': 'Ильич', 'role_id': ''}
    response = client.post(f'/users/{default_user_id}/edit', data=payload, follow_redirects=True)

    assert response.request.path == '/'
    assert 'Пользователь успешно обновлён.' in response.text

    with app.app_context():
        user = db.session.get(User, default_user_id)
        assert user.last_name == 'Смирнов'
        assert user.first_name == 'Петр'
        assert user.middle_name == 'Ильич'


def test_delete_user_requires_auth(client, default_user_id):
    response = client.post(f'/users/{default_user_id}/delete', follow_redirects=True)

    assert response.request.path == '/login'


def test_delete_user_success(client, app):
    login(client)

    with app.app_context():
        role = Role.query.first()
        user = User(login='todelete1', first_name='A', last_name='B', middle_name='C', role=role)
        user.set_password('StrongPass1!')
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    response = client.post(f'/users/{user_id}/delete', follow_redirects=True)

    assert response.request.path == '/'
    assert 'Пользователь успешно удалён.' in response.text

    with app.app_context():
        assert db.session.get(User, user_id) is None


def test_delete_modal_contains_user_name(client):
    login(client)
    response = client.get('/')

    assert 'Вы уверены, что хотите удалить пользователя Пользователь Тест Лабораторный?' in response.text


def test_change_password_requires_auth(client):
    response = client.get('/change-password', follow_redirects=True)

    assert response.request.path == '/login'


def test_change_password_rejects_wrong_old_password(client):
    login(client)
    response = client.post(
        '/change-password',
        data={'old_password': 'bad', 'new_password': 'NewStrong1!', 'new_password_confirm': 'NewStrong1!'},
        follow_redirects=True,
    )

    assert 'Старый пароль введён неверно.' in response.text
    assert 'is-invalid' in response.text


def test_change_password_rejects_mismatch(client):
    login(client)
    response = client.post(
        '/change-password',
        data={'old_password': 'qwerty', 'new_password': 'NewStrong1!', 'new_password_confirm': 'Mismatch1!'},
        follow_redirects=True,
    )

    assert 'Новые пароли не совпадают.' in response.text


def test_change_password_success_and_new_password_works(client):
    login(client)

    response = client.post(
        '/change-password',
        data={'old_password': 'qwerty', 'new_password': 'NewStrong1!', 'new_password_confirm': 'NewStrong1!'},
        follow_redirects=True,
    )

    assert response.request.path == '/'
    assert 'Пароль успешно изменён.' in response.text

    client.get('/logout', follow_redirects=True)
    response_login = client.post('/login', data={'login': 'user', 'password': 'NewStrong1!'}, follow_redirects=True)
    assert 'Вход выполнен успешно.' in response_login.text


def test_remember_me_sets_cookie(client):
    response = client.post('/login', data={'login': 'user', 'password': 'qwerty', 'remember': 'on'}, follow_redirects=False)
    set_cookie_headers = response.headers.getlist('Set-Cookie')

    assert any('remember_token=' in header for header in set_cookie_headers)
    assert any('Expires=' in header for header in set_cookie_headers)
