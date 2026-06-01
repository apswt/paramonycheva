import csv
import io

from flask import Blueprint, Response, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func

try:
    from .app import (
        RIGHT_VIEW_LOG_REPORTS,
        RIGHT_VIEW_LOGS,
        User,
        VisitLog,
        check_rights,
        db,
        has_right,
    )
except ImportError:
    from app import (
        RIGHT_VIEW_LOG_REPORTS,
        RIGHT_VIEW_LOGS,
        User,
        VisitLog,
        check_rights,
        db,
        has_right,
    )

reports_bp = Blueprint('reports', __name__, url_prefix='/visits')


def _build_csv_response(headers, rows, filename):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)

    content = '\ufeff' + output.getvalue()
    return Response(
        content,
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )


def _user_label(user):
    if user is None:
        return 'Неаутентифицированный пользователь'
    return user.full_name


@reports_bp.route('/')
@login_required
@check_rights(RIGHT_VIEW_LOGS)
def visit_logs():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    if page < 1:
        page = 1
    if per_page < 1 or per_page > 100:
        per_page = 10

    logs_query = VisitLog.query.order_by(VisitLog.created_at.desc(), VisitLog.id.desc())

    if not has_right(current_user, RIGHT_VIEW_LOG_REPORTS):
        logs_query = logs_query.filter(VisitLog.user_id == current_user.id)

    pagination = logs_query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        'visit_logs.html',
        title='Журнал посещений',
        pagination=pagination,
        show_reports=has_right(current_user, RIGHT_VIEW_LOG_REPORTS),
        guest_label='Неаутентифицированный пользователь',
    )


@reports_bp.route('/reports/pages')
@login_required
@check_rights(RIGHT_VIEW_LOG_REPORTS)
def pages_report():
    stats = (
        db.session.query(
            VisitLog.path.label('path'),
            func.count(VisitLog.id).label('visit_count'),
        )
        .group_by(VisitLog.path)
        .order_by(func.count(VisitLog.id).desc(), VisitLog.path.asc())
        .all()
    )

    return render_template(
        'report_pages.html',
        title='Отчёт по страницам',
        stats=stats,
    )


@reports_bp.route('/reports/pages/export')
@login_required
@check_rights(RIGHT_VIEW_LOG_REPORTS)
def pages_report_export():
    stats = (
        db.session.query(
            VisitLog.path.label('path'),
            func.count(VisitLog.id).label('visit_count'),
        )
        .group_by(VisitLog.path)
        .order_by(func.count(VisitLog.id).desc(), VisitLog.path.asc())
        .all()
    )

    rows = [(row.path, row.visit_count) for row in stats]
    return _build_csv_response(
        headers=['Страница', 'Количество посещений'],
        rows=rows,
        filename='visits_by_pages.csv',
    )


@reports_bp.route('/reports/users')
@login_required
@check_rights(RIGHT_VIEW_LOG_REPORTS)
def users_report():
    grouped = (
        db.session.query(
            VisitLog.user_id.label('user_id'),
            func.count(VisitLog.id).label('visit_count'),
        )
        .group_by(VisitLog.user_id)
        .order_by(func.count(VisitLog.id).desc(), VisitLog.user_id.asc())
        .all()
    )

    user_ids = [row.user_id for row in grouped if row.user_id is not None]
    users = User.query.filter(User.id.in_(user_ids)).all() if user_ids else []
    user_map = {user.id: user for user in users}

    stats = [
        {
            'user_label': _user_label(user_map.get(row.user_id)),
            'visit_count': row.visit_count,
        }
        for row in grouped
    ]

    return render_template(
        'report_users.html',
        title='Отчёт по пользователям',
        stats=stats,
    )


@reports_bp.route('/reports/users/export')
@login_required
@check_rights(RIGHT_VIEW_LOG_REPORTS)
def users_report_export():
    grouped = (
        db.session.query(
            VisitLog.user_id.label('user_id'),
            func.count(VisitLog.id).label('visit_count'),
        )
        .group_by(VisitLog.user_id)
        .order_by(func.count(VisitLog.id).desc(), VisitLog.user_id.asc())
        .all()
    )

    user_ids = [row.user_id for row in grouped if row.user_id is not None]
    users = User.query.filter(User.id.in_(user_ids)).all() if user_ids else []
    user_map = {user.id: user for user in users}

    rows = [(_user_label(user_map.get(row.user_id)), row.visit_count) for row in grouped]
    return _build_csv_response(
        headers=['Пользователь', 'Количество посещений'],
        rows=rows,
        filename='visits_by_users.csv',
    )
