from datetime import datetime, timedelta

from app.models import db, Course, Review


def login(client, login_value='user', password='qwerty'):
    return client.post(
        '/auth/login',
        data={'login': login_value, 'password': password},
        follow_redirects=True,
    )


def clear_reviews(course):
    course.rating_sum = 0
    course.rating_num = 0


def seed_reviews(app, course_id, reviewer_ids, rows):
    with app.app_context():
        course = db.session.get(Course, course_id)
        db.session.execute(db.delete(Review))
        clear_reviews(course)

        for idx, row in enumerate(rows):
            rating, text, created_at = row
            review = Review(
                rating=rating,
                text=text,
                created_at=created_at,
                course_id=course_id,
                user_id=reviewer_ids[idx],
            )
            db.session.add(review)
            course.rating_sum += rating
            course.rating_num += 1

        db.session.commit()


def test_course_page_shows_last_five_reviews(app, client, seed_data):
    base = datetime(2026, 1, 1, 10, 0, 0)
    rows = [(idx % 6, f'Отзыв #{idx}', base + timedelta(minutes=idx)) for idx in range(1, 7)]
    seed_reviews(app, seed_data['course_id'], seed_data['reviewer_ids'], rows)

    response = client.get(f"/courses/{seed_data['course_id']}")

    assert response.status_code == 200
    assert 'Отзыв #6' in response.text
    assert 'Отзыв #5' in response.text
    assert 'Отзыв #4' in response.text
    assert 'Отзыв #3' in response.text
    assert 'Отзыв #2' in response.text
    assert 'Отзыв #1' not in response.text
    assert 'Фамилия5 Имя5 Отчество5' in response.text
    assert '01.01.2026 10:06' in response.text
    assert 'Оценка:' in response.text


def test_course_page_contains_all_reviews_button(client, seed_data):
    response = client.get(f"/courses/{seed_data['course_id']}")

    assert response.status_code == 200
    assert f'/courses/{seed_data["course_id"]}/reviews' in response.text
    assert 'Все отзывы' in response.text


def test_reviews_default_sorted_by_newest(app, client, seed_data):
    base = datetime(2026, 2, 1, 10, 0, 0)
    rows = [
        (5, 'Старый отзыв', base),
        (4, 'Новый отзыв', base + timedelta(days=1)),
    ]
    seed_reviews(app, seed_data['course_id'], seed_data['reviewer_ids'], rows)

    response = client.get(f"/courses/{seed_data['course_id']}/reviews")

    assert response.status_code == 200
    assert response.text.index('Новый отзыв') < response.text.index('Старый отзыв')


def test_reviews_can_be_sorted_positive_first(app, client, seed_data):
    base = datetime(2026, 2, 2, 12, 0, 0)
    rows = [
        (1, 'Низкая оценка', base),
        (5, 'Высокая оценка', base + timedelta(minutes=1)),
        (3, 'Средняя оценка', base + timedelta(minutes=2)),
    ]
    seed_reviews(app, seed_data['course_id'], seed_data['reviewer_ids'], rows)

    response = client.get(f"/courses/{seed_data['course_id']}/reviews?sort=positive")

    assert response.status_code == 200
    assert response.text.index('Высокая оценка') < response.text.index('Средняя оценка')
    assert response.text.index('Средняя оценка') < response.text.index('Низкая оценка')


def test_reviews_can_be_sorted_negative_first(app, client, seed_data):
    base = datetime(2026, 2, 3, 12, 0, 0)
    rows = [
        (5, 'Пятерка', base),
        (0, 'Ноль', base + timedelta(minutes=1)),
        (2, 'Двойка', base + timedelta(minutes=2)),
    ]
    seed_reviews(app, seed_data['course_id'], seed_data['reviewer_ids'], rows)

    response = client.get(f"/courses/{seed_data['course_id']}/reviews?sort=negative")

    assert response.status_code == 200
    assert response.text.index('Ноль') < response.text.index('Двойка')
    assert response.text.index('Двойка') < response.text.index('Пятерка')


def test_reviews_pagination_keeps_sort_param(app, client, seed_data):
    base = datetime(2026, 2, 4, 8, 0, 0)
    rows = []
    for i in range(1, 13):
        rows.append((i % 6, f'Пагинация отзыв {i}', base + timedelta(minutes=i)))
    seed_reviews(app, seed_data['course_id'], seed_data['reviewer_ids'], rows)

    response = client.get(f"/courses/{seed_data['course_id']}/reviews?sort=positive&per_page=5")

    assert response.status_code == 200
    assert 'sort=positive' in response.text
    assert 'per_page=5' in response.text


def test_authenticated_user_sees_review_form(client, seed_data):
    login(client)
    response = client.get(f"/courses/{seed_data['course_id']}")

    assert response.status_code == 200
    assert 'Оставить отзыв' in response.text
    assert 'name="rating"' in response.text
    assert 'name="text"' in response.text


def test_anonymous_user_sees_login_prompt_instead_of_form(client, seed_data):
    response = client.get(f"/courses/{seed_data['course_id']}")

    assert response.status_code == 200
    assert 'Чтобы оставить отзыв' in response.text
    assert 'name="text"' not in response.text


def test_user_with_existing_review_sees_own_review(app, client, seed_data):
    base = datetime(2026, 2, 5, 8, 0, 0)
    rows = [(4, 'Мой отзыв', base)]
    seed_reviews(app, seed_data['course_id'], seed_data['reviewer_ids'], rows)

    login(client)
    response = client.get(f"/courses/{seed_data['course_id']}")

    assert response.status_code == 200
    assert 'Вы уже оставили отзыв к этому курсу.' in response.text
    assert 'Мой отзыв' in response.text
    assert 'name="text"' not in response.text


def test_create_review_updates_course_rating(app, client, seed_data):
    login(client)
    response = client.post(
        f"/courses/{seed_data['course_id']}/reviews/create",
        data={'rating': '4', 'text': 'Отличный курс', 'next_page': 'show', 'sort': 'newest'},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert 'Отзыв успешно добавлен.' in response.text

    with app.app_context():
        course = db.session.get(Course, seed_data['course_id'])
        review = db.session.execute(
            db.select(Review).where(
                Review.course_id == seed_data['course_id'],
                Review.user_id == seed_data['base_user_id'],
            )
        ).scalar()
        assert review is not None
        assert review.rating == 4
        assert course.rating_sum == 4
        assert course.rating_num == 1


def test_duplicate_review_is_blocked(app, client, seed_data):
    base = datetime(2026, 2, 6, 8, 0, 0)
    rows = [(2, 'Первый отзыв', base)]
    seed_reviews(app, seed_data['course_id'], seed_data['reviewer_ids'], rows)

    login(client)
    response = client.post(
        f"/courses/{seed_data['course_id']}/reviews/create",
        data={'rating': '5', 'text': 'Повторный отзыв', 'next_page': 'show', 'sort': 'newest'},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert 'Вы уже оставили отзыв к этому курсу.' in response.text

    with app.app_context():
        course = db.session.get(Course, seed_data['course_id'])
        reviews = db.session.execute(
            db.select(Review).where(Review.course_id == seed_data['course_id'])
        ).scalars().all()
        assert len(reviews) == 1
        assert course.rating_sum == 2
        assert course.rating_num == 1


def test_invalid_rating_returns_error(client, seed_data):
    login(client)
    response = client.post(
        f"/courses/{seed_data['course_id']}/reviews/create",
        data={'rating': 'abc', 'text': 'Текст', 'next_page': 'show', 'sort': 'newest'},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert 'Некорректная оценка. Выберите значение от 0 до 5.' in response.text


def test_empty_text_returns_error(client, seed_data):
    login(client)
    response = client.post(
        f"/courses/{seed_data['course_id']}/reviews/create",
        data={'rating': '5', 'text': '   ', 'next_page': 'show', 'sort': 'newest'},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert 'Текст отзыва не может быть пустым.' in response.text


def test_create_review_from_all_reviews_redirects_back(client, seed_data):
    login(client)
    response = client.post(
        f"/courses/{seed_data['course_id']}/reviews/create",
        data={'rating': '3', 'text': 'Отзыв со страницы всех', 'next_page': 'all_reviews', 'sort': 'negative'},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers['Location'].endswith(
        f"/courses/{seed_data['course_id']}/reviews?sort=negative"
    )


def test_reviews_page_for_unknown_course_returns_404(client):
    response = client.get('/courses/99999/reviews')
    assert response.status_code == 404


def test_rating_selector_contains_all_required_options(client, seed_data):
    login(client)
    response = client.get(f"/courses/{seed_data['course_id']}")

    assert 'value="5"' in response.text and 'отлично' in response.text
    assert 'value="4"' in response.text and 'хорошо' in response.text
    assert 'value="3"' in response.text and 'удовлетворительно' in response.text
    assert 'value="2"' in response.text and 'неудовлетворительно' in response.text
    assert 'value="1"' in response.text and 'плохо' in response.text
    assert 'value="0"' in response.text and 'ужасно' in response.text
