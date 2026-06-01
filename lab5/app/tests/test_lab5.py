from datetime import datetime, timedelta

from app import ROLE_ADMIN, ROLE_USER, Role, User, VisitLog, db


def login(client, login_value, password, follow_redirects=True, next_url=None, remember=False):
    data = {'login': login_value, 'password': password}
    if remember:
        data['remember'] = 'on'

    url = '/login'
    if next_url:
        url += f'?next={next_url}'

    return client.post(url, data=data, follow_redirects=follow_redirects)


def login_admin(client, follow_redirects=True, remember=False, next_url=None):
    return login(
        client,
        login_value='admin',
        password='Admin123!',
        follow_redirects=follow_redirects,
        next_url=next_url,
        remember=remember,
    )


def login_regular(client, follow_redirects=True, remember=False, next_url=None):
    return login(
        client,
        login_value='user01',
        password='User123!',
        follow_redirects=follow_redirects,
        next_url=next_url,
        remember=remember,
    )


def clear_and_seed_logs(app, rows):
    with app.app_context():
        VisitLog.query.delete()
        for path, user_id, created_at in rows:
            db.session.add(VisitLog(path=path, user_id=user_id, created_at=created_at))
        db.session.commit()


def test_index_hides_management_actions_for_anonymous(client):
    response = client.get('/')

    assert response.status_code == 200
    assert 'Создание пользователя' not in response.text
    assert 'Редактирование' not in response.text
    assert 'Удаление' not in response.text


def test_index_shows_admin_management_actions(client):
    login_admin(client)
    response = client.get('/')

    assert 'Создание пользователя' in response.text
    assert 'Редактирование' in response.text
    assert 'Удаление' in response.text


def test_regular_user_can_edit_only_self_on_index(client, user_ids):
    login_regular(client)
    response = client.get('/')

    assert f'/users/{user_ids["regular"]}/edit' in response.text
    assert f'/users/{user_ids["admin"]}/edit' not in response.text
    assert f'/users/{user_ids["regular"]}' in response.text
    assert f'/users/{user_ids["admin"]}' not in response.text


def test_regular_user_cannot_open_other_profile(client, user_ids):
    login_regular(client)
    response = client.get(f'/users/{user_ids["admin"]}', follow_redirects=True)

    assert response.request.path == '/'
    assert 'У вас недостаточно прав для доступа к данной странице.' in response.text


def test_regular_user_can_open_own_profile(client, user_ids):
    login_regular(client)
    response = client.get(f'/users/{user_ids["regular"]}')

    assert response.status_code == 200
    assert 'Просмотр пользователя' in response.text
    assert 'user01' in response.text


def test_regular_user_cannot_open_create_user_page(client):
    login_regular(client)
    response = client.get('/users/create', follow_redirects=True)

    assert response.request.path == '/'
    assert 'У вас недостаточно прав для доступа к данной странице.' in response.text


def test_admin_can_create_user(client, app):
    login_admin(client)

    with app.app_context():
        user_role = Role.query.filter_by(name=ROLE_USER).first()

    response = client.post(
        '/users/create',
        data={
            'login': 'newuser5',
            'password': 'StrongPass1!',
            'last_name': 'Новый',
            'first_name': 'Пользователь',
            'middle_name': 'Тестовый',
            'role_id': str(user_role.id),
        },
        follow_redirects=True,
    )

    assert response.request.path == '/'
    assert 'Пользователь успешно создан.' in response.text

    with app.app_context():
        created = User.query.filter_by(login='newuser5').first()
        assert created is not None
        assert created.role.name == ROLE_USER


def test_regular_user_edit_form_has_disabled_role_field(client, user_ids):
    login_regular(client)
    response = client.get(f'/users/{user_ids["regular"]}/edit')

    assert response.status_code == 200
    assert 'name="role_id"' in response.text
    assert 'disabled' in response.text


def test_regular_user_cannot_change_own_role(client, app, user_ids):
    login_regular(client)

    with app.app_context():
        admin_role = Role.query.filter_by(name=ROLE_ADMIN).first()

    response = client.post(
        f'/users/{user_ids["regular"]}/edit',
        data={
            'last_name': 'Пользователь',
            'first_name': 'Обычный',
            'middle_name': 'Тестовый',
            'role_id': str(admin_role.id),
        },
        follow_redirects=True,
    )

    assert response.request.path == '/'
    assert 'Пользователь успешно обновлён.' in response.text

    with app.app_context():
        user = db.session.get(User, user_ids['regular'])
        assert user.role.name == ROLE_USER


def test_admin_can_delete_user(client, app):
    login_admin(client)

    with app.app_context():
        user_role = Role.query.filter_by(name=ROLE_USER).first()
        user = User(login='delete55', first_name='Удалить', last_name='Меня', middle_name='Тест', role=user_role)
        user.set_password('StrongPass1!')
        db.session.add(user)
        db.session.commit()
        target_id = user.id

    response = client.post(f'/users/{target_id}/delete', follow_redirects=True)

    assert response.request.path == '/'
    assert 'Пользователь успешно удалён.' in response.text

    with app.app_context():
        assert db.session.get(User, target_id) is None


def test_visit_log_written_on_request(client, app):
    with app.app_context():
        before_count = VisitLog.query.count()

    client.get('/')

    with app.app_context():
        after_count = VisitLog.query.count()

    assert after_count == before_count + 1


def test_visit_logs_requires_authentication(client):
    response = client.get('/visits/', follow_redirects=True)

    assert response.request.path == '/login'
    assert 'Для доступа к запрашиваемой странице необходимо пройти процедуру аутентификации.' in response.text


def test_regular_user_visit_logs_show_only_own_rows(client, app, user_ids):
    login_regular(client)

    base_time = datetime(2026, 1, 1, 10, 0, 0)
    clear_and_seed_logs(
        app,
        [
            ('/only-me', user_ids['regular'], base_time),
            ('/admin-only', user_ids['admin'], base_time + timedelta(seconds=1)),
            ('/guest-only', None, base_time + timedelta(seconds=2)),
        ],
    )

    response = client.get('/visits/')

    assert response.status_code == 200
    assert '/only-me' in response.text
    assert '/admin-only' not in response.text
    assert '/guest-only' not in response.text
    assert 'Отчёт по страницам' not in response.text


def test_admin_visit_logs_show_all_rows_and_links(client, app, user_ids):
    login_admin(client)

    base_time = datetime(2026, 1, 2, 9, 0, 0)
    clear_and_seed_logs(
        app,
        [
            ('/admin-page', user_ids['admin'], base_time),
            ('/regular-page', user_ids['regular'], base_time + timedelta(seconds=1)),
            ('/guest-page', None, base_time + timedelta(seconds=2)),
        ],
    )

    response = client.get('/visits/')

    assert response.status_code == 200
    assert '/admin-page' in response.text
    assert '/regular-page' in response.text
    assert '/guest-page' in response.text
    assert 'Отчёт по страницам' in response.text
    assert 'Отчёт по пользователям' in response.text


def test_regular_user_cannot_open_page_report(client):
    login_regular(client)
    response = client.get('/visits/reports/pages', follow_redirects=True)

    assert response.request.path == '/'
    assert 'У вас недостаточно прав для доступа к данной странице.' in response.text


def test_admin_page_report_sorted_desc(client, app, user_ids):
    login_admin(client)

    base_time = datetime(2026, 1, 3, 12, 0, 0)
    clear_and_seed_logs(
        app,
        [
            ('/popular', user_ids['admin'], base_time),
            ('/popular', user_ids['regular'], base_time + timedelta(seconds=1)),
            ('/rare', None, base_time + timedelta(seconds=2)),
        ],
    )

    response = client.get('/visits/reports/pages')

    assert response.status_code == 200
    assert response.text.index('/popular') < response.text.index('/rare')
    assert '2' in response.text
    assert '1' in response.text


def test_page_report_csv_export(client, app, user_ids):
    login_admin(client)

    base_time = datetime(2026, 1, 4, 8, 0, 0)
    clear_and_seed_logs(
        app,
        [
            ('/csv-page', user_ids['admin'], base_time),
            ('/csv-page', user_ids['regular'], base_time + timedelta(seconds=1)),
        ],
    )

    response = client.get('/visits/reports/pages/export')

    assert response.status_code == 200
    assert response.mimetype == 'text/csv'
    assert 'attachment; filename=visits_by_pages.csv' in response.headers.get('Content-Disposition', '')
    assert 'Страница,Количество посещений' in response.text
    assert '/csv-page,2' in response.text


def test_admin_user_report_contains_guest_row(client, app, user_ids):
    login_admin(client)

    base_time = datetime(2026, 1, 5, 15, 0, 0)
    clear_and_seed_logs(
        app,
        [
            ('/a', user_ids['regular'], base_time),
            ('/b', None, base_time + timedelta(seconds=1)),
        ],
    )

    response = client.get('/visits/reports/users')

    assert response.status_code == 200
    assert 'Неаутентифицированный пользователь' in response.text
    assert 'Пользователь Обычный Тестовый' in response.text


def test_user_report_csv_export(client, app, user_ids):
    login_admin(client)

    base_time = datetime(2026, 1, 6, 10, 0, 0)
    clear_and_seed_logs(
        app,
        [
            ('/x', user_ids['admin'], base_time),
            ('/y', None, base_time + timedelta(seconds=1)),
        ],
    )

    response = client.get('/visits/reports/users/export')

    assert response.status_code == 200
    assert response.mimetype == 'text/csv'
    assert 'attachment; filename=visits_by_users.csv' in response.headers.get('Content-Disposition', '')
    assert 'Пользователь,Количество посещений' in response.text
    assert 'Неаутентифицированный пользователь,1' in response.text


def test_visit_logs_pagination(client, app, user_ids):
    login_admin(client)

    base_time = datetime(2026, 1, 7, 9, 0, 0)
    rows = []
    for i in range(12):
        rows.append((f'/page-{i}', user_ids['admin'], base_time + timedelta(seconds=i)))

    clear_and_seed_logs(app, rows)

    response = client.get('/visits/?page=3&per_page=5')

    assert response.status_code == 200
    assert '/page-1' in response.text
    assert '/page-0' in response.text
    assert '/page-11' not in response.text


def test_unauthorized_redirect_then_login_goes_to_requested_page(client):
    response = client.get('/visits/reports/pages', follow_redirects=True)

    assert response.request.path == '/login'

    response = login_admin(client, follow_redirects=True, next_url='/visits/reports/pages')

    assert response.request.path == '/visits/reports/pages'
    assert 'Вход выполнен успешно.' in response.text


def test_remember_me_sets_cookie(client):
    response = login_admin(client, follow_redirects=False, remember=True)
    set_cookie_headers = response.headers.getlist('Set-Cookie')

    assert any('remember_token=' in header for header in set_cookie_headers)
    assert any('Expires=' in header for header in set_cookie_headers)
