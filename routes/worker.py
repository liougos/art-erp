from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, send_from_directory
from flask_login import login_required, current_user
from datetime import datetime, date
from models import db, DailyReport, Project, ProjectTeamMember, Employee, LeaveRequest, LeaveBalance

worker_bp = Blueprint('worker', __name__)


def _get_worker_employee():
    """Return Employee linked to current user, or None."""
    return current_user.employee if current_user.employee_id else None


def _require_worker(f):
    """Decorator: only allow workers (or admins seeing on behalf of)."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.role not in ('worker', 'admin', 'manager'):
            flash('Δεν έχετε πρόσβαση.', 'danger')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated


@worker_bp.route('/')
@login_required
@_require_worker
def dashboard():
    emp = _get_worker_employee()
    if not emp and current_user.role == 'worker':
        flash('Ο λογαριασμός σας δεν έχει συνδεθεί με υπάλληλο. Επικοινωνήστε με τον διαχειριστή.', 'warning')
        return render_template('worker/dashboard.html', assignments=[], reports=[], emp=None)

    if emp:
        assignments = ProjectTeamMember.query.filter_by(employee_id=emp.id).all()
        reports = DailyReport.query.filter_by(employee_id=emp.id)\
            .order_by(DailyReport.report_date.desc()).limit(20).all()
    else:
        # Admin/manager viewing the worker portal — show all
        assignments = ProjectTeamMember.query.all()
        reports = DailyReport.query.order_by(DailyReport.report_date.desc()).limit(30).all()

    today = date.today()
    today_reports = [r for r in reports if r.report_date == today]
    return render_template('worker/dashboard.html',
                           assignments=assignments, reports=reports,
                           today_reports=today_reports, emp=emp, today=today)


@worker_bp.route('/report/new', methods=['GET', 'POST'])
@login_required
@_require_worker
def new_report():
    emp = _get_worker_employee()
    is_manager = current_user.role in ('admin', 'manager')

    # Workers must be linked to an employee record
    if not emp and not is_manager:
        flash('Ο λογαριασμός σας δεν έχει συνδεθεί με υπάλληλο.', 'danger')
        return redirect(url_for('worker.dashboard'))

    # Manager/admin can select any active project + any employee
    if is_manager:
        projects_all = Project.query.filter(
            Project.status.in_(['active', 'planning'])
        ).order_by(Project.code).all()
        employees_all = Employee.query.filter_by(status='active').order_by(Employee.last_name).all()
        assignments = []  # not used in manager mode
    else:
        assignments = ProjectTeamMember.query.filter_by(employee_id=emp.id).all()
        projects_all = None
        employees_all = None

    if request.method == 'POST':
        project_id = request.form.get('project_id')
        if not project_id:
            flash('Επιλέξτε έργο.', 'danger')
            return redirect(request.url)

        # Manager can choose which employee's report this is
        if is_manager:
            emp_id_form = request.form.get('employee_id')
            target_emp = Employee.query.get(emp_id_form) if emp_id_form else emp
        else:
            target_emp = emp

        if not target_emp:
            flash('Επιλέξτε εργαζόμενο.', 'danger')
            return redirect(request.url)

        report_date_str = request.form.get('report_date', str(date.today()))
        report_date = datetime.strptime(report_date_str, '%Y-%m-%d').date()

        # Prevent duplicate for same day + project + employee
        exists = DailyReport.query.filter_by(
            employee_id=target_emp.id, project_id=project_id, report_date=report_date
        ).first()
        if exists:
            flash('Υπάρχει ήδη αναφορά για αυτό το έργο/εργαζόμενο την ίδια ημέρα.', 'warning')
            return redirect(url_for('worker.dashboard'))

        r = DailyReport(
            project_id=project_id,
            employee_id=target_emp.id,
            submitted_by=current_user.id,
            report_date=report_date,
            work_done=request.form.get('work_done', '').strip(),
            hours_worked=request.form.get('hours_worked') or 8,
            workers_present=request.form.get('workers_present') or 1,
            weather=request.form.get('weather', '').strip(),
            problems=request.form.get('problems', '').strip(),
            materials_used=request.form.get('materials_used', '').strip(),
            next_steps=request.form.get('next_steps', '').strip(),
            progress_pct=request.form.get('progress_pct') or None,
            # Managers submit as auto-approved
            status='approved' if is_manager else 'pending',
        )
        db.session.add(r)
        db.session.commit()
        flash('Η αναφορά υποβλήθηκε επιτυχώς!', 'success')
        return redirect(url_for('worker.dashboard'))

    today = date.today()
    return render_template('worker/new_report.html',
                           assignments=assignments, emp=emp, today=today,
                           is_manager=is_manager,
                           projects_all=projects_all, employees_all=employees_all)


@worker_bp.route('/report/<int:id>')
@login_required
@_require_worker
def view_report(id):
    report = DailyReport.query.get_or_404(id)
    emp = _get_worker_employee()
    # Workers can only see their own reports
    if current_user.role == 'worker' and emp and report.employee_id != emp.id:
        flash('Δεν έχετε πρόσβαση σε αυτή την αναφορά.', 'danger')
        return redirect(url_for('worker.dashboard'))
    return render_template('worker/view_report.html', report=report)


# ── Manager routes ──────────────────────────────────────────────────────────

@worker_bp.route('/reports')
@login_required
def all_reports():
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε πρόσβαση.', 'danger')
        return redirect(url_for('dashboard.index'))

    project_id = request.args.get('project_id', '')
    status = request.args.get('status', '')
    employee_id = request.args.get('employee_id', '')

    q = DailyReport.query
    if project_id: q = q.filter_by(project_id=project_id)
    if status: q = q.filter_by(status=status)
    if employee_id: q = q.filter_by(employee_id=employee_id)

    reports = q.order_by(DailyReport.report_date.desc(), DailyReport.created_at.desc()).all()
    projects = Project.query.order_by(Project.code).all()
    employees = Employee.query.filter_by(status='active').order_by(Employee.last_name).all()

    pending_count = DailyReport.query.filter_by(status='pending').count()

    return render_template('worker/all_reports.html',
                           reports=reports, projects=projects, employees=employees,
                           pending_count=pending_count,
                           project_id=project_id, status=status, employee_id=employee_id)


@worker_bp.route('/leave')
@login_required
@_require_worker
def my_leaves():
    emp = _get_worker_employee()
    if not emp:
        flash('Ο λογαριασμός σας δεν έχει συνδεθεί με υπάλληλο.', 'danger')
        return redirect(url_for('worker.dashboard'))
    leaves = LeaveRequest.query.filter_by(employee_id=emp.id)\
        .order_by(LeaveRequest.created_at.desc()).all()
    year = date.today().year
    balance = LeaveBalance.query.filter_by(employee_id=emp.id, year=year).first()
    return render_template('worker/leave.html', emp=emp, leaves=leaves, balance=balance, today=date.today())


@worker_bp.route('/leave/new', methods=['POST'])
@login_required
@_require_worker
def new_leave():
    emp = _get_worker_employee()
    if not emp:
        flash('Ο λογαριασμός σας δεν έχει συνδεθεί με υπάλληλο.', 'danger')
        return redirect(url_for('worker.dashboard'))

    from datetime import timedelta
    sd = request.form.get('start_date')
    ed = request.form.get('end_date')
    if not sd or not ed:
        flash('Επιλέξτε ημερομηνίες.', 'danger')
        return redirect(url_for('worker.my_leaves'))

    start = datetime.strptime(sd, '%Y-%m-%d').date()
    end = datetime.strptime(ed, '%Y-%m-%d').date()
    if end < start:
        flash('Η ημ/νια λήξης πρέπει να είναι μετά την έναρξη.', 'danger')
        return redirect(url_for('worker.my_leaves'))

    # Count working days
    days = 0
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            days += 1
        cur += timedelta(days=1)

    leave_type = request.form.get('leave_type', 'annual')

    # Check balance for annual leave
    if leave_type == 'annual':
        year = start.year
        bal = LeaveBalance.query.filter_by(employee_id=emp.id, year=year).first()
        total = emp.annual_leave_days or 20
        used = bal.used_days if bal else 0
        remaining = total - used
        if days > remaining:
            flash(f'Δεν έχετε αρκετές άδειες. Υπόλοιπο: {remaining} ημέρες, ζητάτε: {days}.', 'danger')
            return redirect(url_for('worker.my_leaves'))

    leave = LeaveRequest(
        employee_id=emp.id,
        leave_type=leave_type,
        start_date=start,
        end_date=end,
        working_days=days,
        reason=request.form.get('reason', '').strip(),
        status='pending',
    )
    db.session.add(leave)
    db.session.commit()

    # Notify admin
    try:
        from services.email_service import notify_leave_request
        from flask import current_app
        notify_leave_request(leave, current_app.config.get('ADMIN_EMAIL', ''))
    except Exception:
        pass

    flash(f'Αίτηση άδειας υποβλήθηκε ({days} εργάσιμες ημέρες). Αναμένετε έγκριση.', 'success')
    return redirect(url_for('worker.my_leaves'))


@worker_bp.route('/contract')
@login_required
@_require_worker
def view_contract():
    emp = _get_worker_employee()
    if not emp:
        flash('Ο λογαριασμός σας δεν έχει συνδεθεί με υπάλληλο.', 'danger')
        return redirect(url_for('worker.dashboard'))
    if not emp.contract_file_path:
        flash('Δεν υπάρχει ανεβασμένη σύμβαση εργασίας.', 'warning')
        return redirect(url_for('worker.dashboard'))
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], emp.contract_file_path)


@worker_bp.route('/report/<int:id>/review', methods=['POST'])
@login_required
def review_report(id):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε πρόσβαση.', 'danger')
        return redirect(url_for('dashboard.index'))

    report = DailyReport.query.get_or_404(id)
    action = request.form.get('action')
    report.status = 'approved' if action == 'approve' else 'rejected'
    report.reviewer_id = current_user.id
    report.reviewer_notes = request.form.get('reviewer_notes', '').strip()
    report.reviewed_at = datetime.utcnow()
    db.session.commit()
    flash(f'Αναφορά {"εγκρίθηκε" if report.status == "approved" else "απορρίφθηκε"}.', 'success')
    return redirect(url_for('worker.all_reports'))
