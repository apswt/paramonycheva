
def login(client, remember=False, next_url=None, follow_redirects=True):
    data = {'username': 'user', 'password': 'qwerty'}
    if remember:
        data['remember'] = 'on'

    url = '/login'
    if next_url:
        url += f'?next={next_url}'

    return client.post(url, data=data, follow_redirects=follow_redirects)


def test_visit_counter_increments_for_same_client(client):
    response1 = client.get('/visit-counter')
    response2 = client.get('/visit-counter')

    assert '1 раз(а)' in response1.text
    assert '2 раз(а)' in response2.text


def test_visit_counter_is_separate_for_different_clients(app):
    client1 = app.test_client()
    client2 = app.test_client()

    response1 = client1.get('/visit-counter')
    response2 = client2.get('/visit-counter')

    assert '1 раз(а)' in response1.text
    assert '1 раз(а)' in response2.text


def test_successful_login_redirects_to_index_and_shows_message(client):
    response = login(client)

    assert response.request.path == '/'
    assert 'Вход выполнен успешно.' in response.text


def test_successful_login_follow_redirect_chain(client):
    response = login(client, follow_redirects=True)

    assert len(response.history) == 1
    assert response.history[0].status_code == 302
    assert response.history[0].headers['Location'] == '/'


def test_failed_login_stays_on_login_page_and_shows_error(client):
    response = client.post('/login', data={'username': 'user', 'password': 'wrong'}, follow_redirects=False)

    assert response.status_code == 401
    assert 'Неверный логин или пароль.' in response.text
    assert '<h1 class="mb-4">Вход</h1>' in response.text


def test_authenticated_user_can_access_secret_page(client):
    login(client)
    response = client.get('/secret')

    assert response.status_code == 200
    assert 'Секретная страница' in response.text


def test_authenticated_user_can_access_secret_page_via_flask_login_client(auth_client):
    response = auth_client.get('/secret')

    assert response.status_code == 200
    assert 'Секретная страница' in response.text


def test_anonymous_user_redirected_to_login_when_accessing_secret(client):
    response = client.get('/secret', follow_redirects=True)

    assert response.request.path == '/login'
    assert 'Для доступа к запрашиваемой странице необходимо пройти процедуру аутентификации.' in response.text


def test_anonymous_secret_redirect_contains_history(client):
    response = client.get('/secret', follow_redirects=True)

    assert len(response.history) == 1
    assert response.history[0].status_code == 302
    assert '/login?next=%2Fsecret' in response.history[0].headers['Location']
    assert response.request.path == '/login'


def test_user_redirected_to_secret_after_login_with_next(client):
    response = login(client, next_url='/secret')

    assert response.request.path == '/secret'
    assert 'Секретная страница' in response.text


def test_login_ignores_unsafe_next_url(client):
    response = client.post(
        '/login?next=https://evil.example',
        data={'username': 'user', 'password': 'qwerty'},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers['Location'] == '/'


def test_remember_me_sets_remember_cookie(client):
    response = client.post(
        '/login',
        data={'username': 'user', 'password': 'qwerty', 'remember': 'on'},
        follow_redirects=False,
    )
    set_cookie_headers = response.headers.getlist('Set-Cookie')
    remember_headers = [header for header in set_cookie_headers if 'remember_token=' in header]

    assert remember_headers
    assert any('Expires=' in header for header in remember_headers)


def test_navbar_for_anonymous_user_hides_secret_link(client):
    response = client.get('/')

    assert 'Секретная страница' not in response.text
    assert 'Войти' in response.text
    assert 'Счётчик посещений' in response.text


def test_navbar_for_authenticated_user_shows_secret_link(client):
    login(client)
    response = client.get('/')

    assert 'Секретная страница' in response.text
    assert 'Выйти' in response.text
    assert 'Войти' not in response.text


def test_logout_makes_secret_unavailable(client):
    login(client)
    client.get('/logout')

    response = client.get('/secret', follow_redirects=False)
    assert response.status_code == 302
    assert '/login?next=%2Fsecret' in response.headers['Location']


def test_login_page_contains_remember_me_checkbox(client):
    response = client.get('/login')

    assert 'Запомнить меня' in response.text
    assert 'name="remember"' in response.text
