import re
from datetime import datetime

import pytest


@pytest.fixture
def sample_post():
    return {
        'title': 'Заголовок поста',
        'text': 'Полный текст поста для проверки рендеринга страницы поста.',
        'author': 'Toni Hernandez',
        'date': datetime(2020, 8, 22),
        'image_id': '2d2ab7df-cdbc-48a8-a936-35bba702def5.jpg',
        'comments': [
            {
                'author': 'Stephanie Franklin',
                'text': 'Первый комментарий к посту.',
                'replies': [
                    {
                        'author': 'Andrew Mcconnell',
                        'text': 'Ответ на первый комментарий.',
                        'replies': []
                    }
                ]
            }
        ]
    }


@pytest.fixture
def sample_posts(sample_post):
    return [
        sample_post,
        {
            'title': 'Второй пост',
            'text': 'Короткий текст второго поста.',
            'author': 'Maria Petrova',
            'date': datetime(2024, 3, 10),
            'image_id': '7d4e9175-95ea-4c5f-8be5-92a6b708bb3c.jpg',
            'comments': []
        }
    ]


def test_index_page_status_code(client):
    response = client.get('/')
    assert response.status_code == 200


def test_index_page_contains_assignment_text(client):
    response = client.get('/')
    assert 'Задание к лабораторной работе' in response.text


def test_index_page_uses_index_template(client, captured_templates):
    with captured_templates as templates:
        client.get('/')

    assert len(templates) == 1
    template, _ = templates[0]
    assert template.name == 'index.html'


def test_footer_is_present_on_index_page(client):
    response = client.get('/')
    assert 'ФИО: Парамонычева Анастасия Васильевна, группа: 241-372' in response.text


def test_about_page_status_code(client):
    response = client.get('/about')
    assert response.status_code == 200


def test_about_page_uses_about_template_and_title(client, captured_templates):
    with captured_templates as templates:
        client.get('/about')

    assert len(templates) == 1
    template, context = templates[0]
    assert template.name == 'about.html'
    assert context['title'] == 'Об авторе'


def test_posts_page_status_code(client):
    response = client.get('/posts')
    assert response.status_code == 200


def test_posts_page_uses_posts_template_and_context(client, captured_templates, mocker, sample_posts):
    mocker.patch('app.posts_list', return_value=sample_posts, autospec=True)

    with captured_templates as templates:
        client.get('/posts')

    assert len(templates) == 1
    template, context = templates[0]
    assert template.name == 'posts.html'
    assert context['title'] == 'Посты'
    assert context['posts'] == sample_posts


def test_posts_page_contains_posts_data(client, mocker, sample_posts):
    mocker.patch('app.posts_list', return_value=sample_posts, autospec=True)

    response = client.get('/posts')
    assert sample_posts[0]['title'] in response.text
    assert sample_posts[1]['title'] in response.text
    assert sample_posts[0]['author'] in response.text
    assert sample_posts[1]['author'] in response.text


def test_posts_page_contains_links_to_post_pages(client, mocker, sample_posts):
    mocker.patch('app.posts_list', return_value=sample_posts, autospec=True)

    response = client.get('/posts')
    assert 'href="/posts/0"' in response.text
    assert 'href="/posts/1"' in response.text


def test_post_page_status_code(client, mocker, sample_posts):
    mocker.patch('app.posts_list', return_value=sample_posts, autospec=True)

    response = client.get('/posts/0')
    assert response.status_code == 200


def test_post_page_uses_post_template_and_context(client, captured_templates, mocker, sample_posts):
    mocker.patch('app.posts_list', return_value=sample_posts, autospec=True)

    with captured_templates as templates:
        client.get('/posts/0')

    assert len(templates) == 1
    template, context = templates[0]
    assert template.name == 'post.html'
    assert context['title'] == sample_posts[0]['title']
    assert context['post'] == sample_posts[0]


def test_post_page_contains_all_post_data(client, mocker, sample_posts):
    mocker.patch('app.posts_list', return_value=sample_posts, autospec=True)

    response = client.get('/posts/0')
    assert sample_posts[0]['title'] in response.text
    assert sample_posts[0]['author'] in response.text
    assert sample_posts[0]['text'] in response.text
    assert sample_posts[0]['image_id'] in response.text


def test_post_page_publication_date_format(client, mocker, sample_posts):
    mocker.patch('app.posts_list', return_value=sample_posts, autospec=True)

    response = client.get('/posts/0')
    assert re.search(r'\b22\.08\.2020\b', response.text)


def test_post_page_contains_comment_form(client, mocker, sample_posts):
    mocker.patch('app.posts_list', return_value=sample_posts, autospec=True)

    response = client.get('/posts/0')
    assert 'Оставьте комментарий' in response.text
    assert '<textarea' in response.text
    assert 'Отправить' in response.text


def test_post_page_contains_comments_and_replies(client, mocker, sample_posts):
    mocker.patch('app.posts_list', return_value=sample_posts, autospec=True)

    response = client.get('/posts/0')
    assert 'Stephanie Franklin' in response.text
    assert 'Первый комментарий к посту.' in response.text
    assert 'Andrew Mcconnell' in response.text
    assert 'Ответ на первый комментарий.' in response.text


def test_post_page_returns_404_for_nonexistent_post(client, mocker, sample_posts):
    mocker.patch('app.posts_list', return_value=sample_posts, autospec=True)

    response = client.get('/posts/99')
    assert response.status_code == 404
