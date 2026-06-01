from flask import Blueprint, render_template, request, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from app.models import db
from app.repositories import (
    CourseRepository,
    UserRepository,
    CategoryRepository,
    ImageRepository,
    ReviewRepository,
)

user_repository = UserRepository(db)
course_repository = CourseRepository(db)
category_repository = CategoryRepository(db)
image_repository = ImageRepository(db)
review_repository = ReviewRepository(db)

bp = Blueprint('courses', __name__, url_prefix='/courses')

COURSE_PARAMS = [
    'author_id', 'name', 'category_id', 'short_desc', 'full_desc'
]

REVIEW_RATING_OPTIONS = [
    {'value': 5, 'label': 'отлично'},
    {'value': 4, 'label': 'хорошо'},
    {'value': 3, 'label': 'удовлетворительно'},
    {'value': 2, 'label': 'неудовлетворительно'},
    {'value': 1, 'label': 'плохо'},
    {'value': 0, 'label': 'ужасно'},
]

REVIEW_SORT_OPTIONS = [
    {'value': ReviewRepository.SORT_NEWEST, 'label': 'Сначала новые'},
    {'value': ReviewRepository.SORT_POSITIVE, 'label': 'Сначала положительные'},
    {'value': ReviewRepository.SORT_NEGATIVE, 'label': 'Сначала отрицательные'},
]


def params():
    return { p: request.form.get(p) or None for p in COURSE_PARAMS }

def search_params():
    return {
        'name': request.args.get('name'),
        'category_ids': [x for x in request.args.getlist('category_ids') if x],
    }


def review_redirect_url(course_id):
    next_page = request.form.get('next_page')
    sort = review_repository.normalize_sort(request.form.get('sort'))
    if next_page == 'all_reviews':
        return url_for('courses.reviews', course_id=course_id, sort=sort)
    return url_for('courses.show', course_id=course_id)

@bp.route('/')
def index():
    pagination = course_repository.get_pagination_info(**search_params())
    courses = course_repository.get_all_courses(pagination=pagination)
    categories = category_repository.get_all_categories()
    return render_template('courses/index.html',
                           courses=courses,
                           categories=categories,
                           pagination=pagination,
                           search_params=search_params())

@bp.route('/new')
@login_required
def new():
    course = course_repository.new_course()
    categories = category_repository.get_all_categories()
    users = user_repository.get_all_users()
    return render_template('courses/new.html',
                           categories=categories,
                           users=users,
                           course=course)

@bp.route('/create', methods=['POST'])
@login_required
def create():
    f = request.files.get('background_img')
    img = None
    course = None 

    try:
        if f and f.filename:
            img = image_repository.add_image(f)

        image_id = img.id if img else None
        course = course_repository.add_course(**params(), background_image_id=image_id)
    except IntegrityError as err:
        flash(f'Возникла ошибка при записи данных в БД. Проверьте корректность введённых данных. ({err})', 'danger')
        categories = category_repository.get_all_categories()
        users = user_repository.get_all_users()
        return render_template('courses/new.html',
                            categories=categories,
                            users=users,
                            course=course)

    flash(f'Курс {course.name} был успешно добавлен!', 'success')

    return redirect(url_for('courses.index'))

@bp.route('/<int:course_id>')
def show(course_id):
    course = course_repository.get_course_by_id(course_id)
    if course is None:
        abort(404)
    latest_reviews = review_repository.get_recent_reviews_for_course(course_id, limit=5)
    user_review = None
    if current_user.is_authenticated:
        user_review = review_repository.get_user_review(course_id, current_user.id)

    return render_template(
        'courses/show.html',
        course=course,
        latest_reviews=latest_reviews,
        user_review=user_review,
        review_rating_options=REVIEW_RATING_OPTIONS,
    )


@bp.route('/<int:course_id>/reviews')
def reviews(course_id):
    course = course_repository.get_course_by_id(course_id)
    if course is None:
        abort(404)

    sort = review_repository.normalize_sort(request.args.get('sort'))
    pagination = review_repository.get_reviews_pagination(course_id=course_id, sort=sort)
    all_reviews = review_repository.get_reviews_for_course(
        course_id=course_id,
        sort=sort,
        pagination=pagination
    )

    user_review = None
    if current_user.is_authenticated:
        user_review = review_repository.get_user_review(course_id, current_user.id)

    return render_template(
        'courses/reviews.html',
        course=course,
        reviews=all_reviews,
        pagination=pagination,
        sort=sort,
        sort_options=REVIEW_SORT_OPTIONS,
        user_review=user_review,
        review_rating_options=REVIEW_RATING_OPTIONS,
    )


@bp.route('/<int:course_id>/reviews/create', methods=['POST'])
@login_required
def create_review(course_id):
    course = course_repository.get_course_by_id(course_id)
    if course is None:
        abort(404)

    redirect_url = review_redirect_url(course_id)
    current_review = review_repository.get_user_review(course_id, current_user.id)
    if current_review is not None:
        flash('Вы уже оставили отзыв к этому курсу.', 'warning')
        return redirect(redirect_url)

    rating_raw = request.form.get('rating')
    review_text = (request.form.get('text') or '').strip()

    try:
        rating = int(rating_raw)
    except (TypeError, ValueError):
        flash('Некорректная оценка. Выберите значение от 0 до 5.', 'danger')
        return redirect(redirect_url)

    if rating < 0 or rating > 5:
        flash('Некорректная оценка. Выберите значение от 0 до 5.', 'danger')
        return redirect(redirect_url)

    if not review_text:
        flash('Текст отзыва не может быть пустым.', 'danger')
        return redirect(redirect_url)

    try:
        review_repository.create_review(
            course_id=course_id,
            user_id=current_user.id,
            rating=rating,
            text=review_text,
        )
    except IntegrityError:
        db.session.rollback()
        flash('Не удалось сохранить отзыв. Проверьте корректность данных.', 'danger')
        return redirect(redirect_url)

    flash('Отзыв успешно добавлен.', 'success')
    return redirect(redirect_url)
