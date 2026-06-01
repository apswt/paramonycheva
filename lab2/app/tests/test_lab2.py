import pytest

from app import (
    INVALID_CHARS_MESSAGE,
    INVALID_COUNT_MESSAGE,
    TOGGLE_COOKIE_NAME,
    format_phone_number,
    get_phone_error,
)


def test_index_page_status_code(client):
    response = client.get('/')
    assert response.status_code == 200


def test_index_page_contains_sections(client):
    response = client.get('/')
    assert 'Параметры URL' in response.text
    assert 'Проверка телефона' in response.text


def test_url_params_page_status_code(client):
    response = client.get('/url-params')
    assert response.status_code == 200


def test_url_params_page_renders_all_params(client):
    response = client.get('/url-params?name=Anastasia&group=241-372')
    assert 'name' in response.text
    assert 'Anastasia' in response.text
    assert 'group' in response.text
    assert '241-372' in response.text


def test_url_params_page_supports_multiple_values(client):
    response = client.get('/url-params?tag=python&tag=flask')
    assert 'python, flask' in response.text


def test_url_params_template_used(client, captured_templates):
    with captured_templates as templates:
        client.get('/url-params?x=1')

    assert len(templates) == 1
    template, context = templates[0]
    assert template.name == 'url_params.html'
    assert context['title'] == 'Параметры URL'


def test_headers_page_displays_custom_header(client):
    response = client.get('/headers', headers={'X-Test-Header': 'HeaderValue'})
    assert 'X-Test-Header' in response.text
    assert 'HeaderValue' in response.text


def test_headers_template_used(client, captured_templates):
    with captured_templates as templates:
        client.get('/headers')

    assert len(templates) == 1
    template, context = templates[0]
    assert template.name == 'headers.html'
    assert context['title'] == 'Заголовки запроса'


def test_cookies_page_sets_cookie_if_missing(client):
    response = client.get('/cookies')
    set_cookie_headers = response.headers.getlist('Set-Cookie')

    assert any(f'{TOGGLE_COOKIE_NAME}=enabled' in header for header in set_cookie_headers)
    assert 'было установлено' in response.text


def test_cookies_page_deletes_cookie_if_exists(client):
    client.set_cookie(TOGGLE_COOKIE_NAME, 'enabled')
    response = client.get('/cookies')
    set_cookie_headers = response.headers.getlist('Set-Cookie')

    assert any(f'{TOGGLE_COOKIE_NAME}=;' in header for header in set_cookie_headers)
    assert any('Expires=' in header for header in set_cookie_headers)
    assert 'было удалено' in response.text


def test_form_params_page_status_code(client):
    response = client.get('/form-params')
    assert response.status_code == 200


def test_form_params_page_displays_submitted_values(client):
    response = client.post('/form-params', data={'first_name': 'Анастасия', 'message': 'Привет'})

    assert 'first_name = Анастасия' in response.text
    assert 'message = Привет' in response.text


def test_form_params_template_used(client, captured_templates):
    with captured_templates as templates:
        client.post('/form-params', data={'first_name': 'A', 'message': 'B'})

    assert len(templates) == 1
    template, context = templates[0]
    assert template.name == 'form_params.html'
    assert context['title'] == 'Параметры формы'


def test_phone_page_get_status_code(client):
    response = client.get('/phone')
    assert response.status_code == 200


def test_phone_valid_plus7_is_formatted(client):
    response = client.post('/phone', data={'phone': '+7 (123) 456-75-90'})

    assert '8-123-456-75-90' in response.text
    assert INVALID_COUNT_MESSAGE not in response.text
    assert INVALID_CHARS_MESSAGE not in response.text


def test_phone_valid_8_prefix_is_formatted(client):
    response = client.post('/phone', data={'phone': '8(123)4567590'})
    assert '8-123-456-75-90' in response.text


def test_phone_valid_10_digits_is_formatted(client):
    response = client.post('/phone', data={'phone': '123.456.75.90'})
    assert '8-123-456-75-90' in response.text


def test_phone_invalid_chars_shows_error_and_bootstrap_classes(client):
    response = client.post('/phone', data={'phone': '123-ABC-7890'})

    assert INVALID_CHARS_MESSAGE in response.text
    assert 'is-invalid' in response.text
    assert 'invalid-feedback' in response.text


def test_phone_invalid_count_for_plus7_shows_count_error(client):
    response = client.post('/phone', data={'phone': '+7 123 456 78'})
    assert INVALID_COUNT_MESSAGE in response.text


def test_phone_invalid_count_for_other_prefix_shows_count_error(client):
    response = client.post('/phone', data={'phone': '71234567890'})
    assert INVALID_COUNT_MESSAGE in response.text


def test_phone_error_does_not_show_formatted_result(client):
    response = client.post('/phone', data={'phone': '12'})
    assert 'Отформатированный номер' not in response.text


def test_phone_valid_input_has_no_invalid_class(client):
    response = client.post('/phone', data={'phone': '1234567890'})
    assert 'is-invalid' not in response.text


def test_phone_helper_detects_invalid_chars():
    assert get_phone_error('phone123') == INVALID_CHARS_MESSAGE


def test_phone_helper_formats_10_digits():
    assert format_phone_number('1234567890') == '8-123-456-78-90'
