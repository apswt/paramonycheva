from app.models import Review, Course


class ReviewRepository:
    SORT_NEWEST = 'newest'
    SORT_POSITIVE = 'positive'
    SORT_NEGATIVE = 'negative'
    ALLOWED_SORTS = {SORT_NEWEST, SORT_POSITIVE, SORT_NEGATIVE}

    def __init__(self, db):
        self.db = db

    def normalize_sort(self, sort):
        if sort in self.ALLOWED_SORTS:
            return sort
        return self.SORT_NEWEST

    def _ordered_query(self, course_id, sort):
        sort = self.normalize_sort(sort)
        query = self.db.select(Review).filter(Review.course_id == course_id)

        if sort == self.SORT_POSITIVE:
            return query.order_by(Review.rating.desc(), Review.created_at.desc())
        if sort == self.SORT_NEGATIVE:
            return query.order_by(Review.rating.asc(), Review.created_at.desc())

        return query.order_by(Review.created_at.desc())

    def get_recent_reviews_for_course(self, course_id, limit=5):
        query = self._ordered_query(course_id, self.SORT_NEWEST).limit(limit)
        return self.db.session.execute(query).scalars().all()

    def get_reviews_pagination(self, course_id, sort, per_page=None):
        query = self._ordered_query(course_id, sort)
        if per_page:
            return self.db.paginate(query, per_page=per_page)
        return self.db.paginate(query)

    def get_reviews_for_course(self, course_id, sort, pagination=None):
        if pagination is not None:
            return pagination.items
        query = self._ordered_query(course_id, sort)
        return self.db.session.execute(query).scalars().all()

    def get_user_review(self, course_id, user_id):
        query = self.db.select(Review).filter(
            Review.course_id == course_id,
            Review.user_id == user_id,
        )
        return self.db.session.execute(query).scalar()

    def create_review(self, course_id, user_id, rating, text):
        review = Review(course_id=course_id, user_id=user_id, rating=rating, text=text)
        course = self.db.session.get(Course, course_id)

        self.db.session.add(review)
        course.rating_sum += rating
        course.rating_num += 1
        self.db.session.commit()

        return review
