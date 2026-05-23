from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from datetime import date
from models import Project, ProjectTeamMember, LeaveRequest, Employee, ProjectEvent

calendar_bp = Blueprint('calendar', __name__)


@calendar_bp.route('/')
@login_required
def index():
    employees = Employee.query.filter_by(status='active').order_by(Employee.last_name).all()
    projects  = Project.query.filter(Project.status.in_(['active', 'planning'])).order_by(Project.code).all()
    return render_template('calendar/index.html', employees=employees, projects=projects, today=date.today())


@calendar_bp.route('/events')
@login_required
def events():
    """Return all calendar events as FullCalendar JSON."""
    out = []

    # ── Project periods ──────────────────────────────────────────────────────
    for p in Project.query.filter(Project.status.in_(['active', 'planning', 'completed'])).all():
        if p.start_date and p.end_date:
            out.append({
                'id':    f'proj_{p.id}',
                'title': f'[{p.code}] {p.title[:40]}',
                'start': str(p.start_date),
                'end':   str(p.end_date),
                'color': '#c9a84c',
                'url':   f'/projects/{p.id}',
                'extendedProps': {'type': 'project', 'status': p.status},
            })

    # ── Project events / milestones ──────────────────────────────────────────
    for ev in ProjectEvent.query.all():
        out.append({
            'id':    f'event_{ev.id}',
            'title': f'📌 {ev.title}',
            'start': str(ev.start_date),
            'end':   str(ev.end_date) if ev.end_date else str(ev.start_date),
            'color': ev.type_color if hasattr(ev, 'type_color') else '#6c757d',
            'extendedProps': {'type': 'milestone'},
        })

    # ── Approved leave requests ──────────────────────────────────────────────
    for leave in LeaveRequest.query.filter_by(status='approved').all():
        emp_name = leave.employee.full_name if leave.employee else '—'
        out.append({
            'id':    f'leave_{leave.id}',
            'title': f'🏖 {emp_name}',
            'start': str(leave.start_date),
            'end':   str(leave.end_date),
            'color': '#dc3545',
            'extendedProps': {'type': 'leave', 'employee': emp_name},
        })

    # ── Team assignments (project membership periods) ────────────────────────
    for tm in ProjectTeamMember.query.all():
        if not tm.start_date: continue
        emp_name = tm.employee.full_name if tm.employee else '—'
        proj_code = tm.project.code if tm.project else '—'
        out.append({
            'id':    f'team_{tm.id}',
            'title': f'👷 {emp_name} — {proj_code}',
            'start': str(tm.start_date),
            'end':   str(tm.end_date) if tm.end_date else str(date.today()),
            'color': '#0d6efd',
            'extendedProps': {'type': 'assignment', 'employee': emp_name},
        })

    return jsonify(out)
