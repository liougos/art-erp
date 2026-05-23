import os
import json
import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_from_directory, current_app
from flask_login import login_required, current_user
from datetime import datetime, date
from werkzeug.utils import secure_filename
from models import (db, Project, ProjectPhase, ProjectLog, ProjectTeamMember,
                    Invoice, Document, Employee, User, Tender, ProjectMessage,
                    ProjectEvent, MaterialRequest, ProjectPayment, Notification,
                    ProjectPhoto)

logger = logging.getLogger(__name__)

projects_bp = Blueprint('projects', __name__)


@projects_bp.route('/')
@login_required
def index():
    status = request.args.get('status', '')
    q = request.args.get('q', '')
    query = Project.query
    if status: query = query.filter_by(status=status)
    if q: query = query.filter(Project.title.ilike(f'%{q}%'))
    projects = query.order_by(Project.updated_at.desc()).all()
    return render_template('projects/index.html', projects=projects, status=status, q=q)


def _next_project_code():
    year = date.today().year
    count = Project.query.filter(Project.code.like(f'AR-{year}-%')).count()
    return f'AR-{year}-{count+1:03d}'


@projects_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    tenders = Tender.query.filter_by(status='won').order_by(Tender.title).all()
    users = User.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        p = Project(
            code=_next_project_code(),
            title=request.form['title'].strip(),
            description=request.form.get('description', '').strip(),
            tender_id=request.form.get('tender_id') or None,
            contract_type=request.form.get('contract_type', 'public'),
            client_name=request.form.get('client_name', '').strip(),
            client_afm=request.form.get('client_afm', '').strip(),
            client_contact=request.form.get('client_contact', '').strip(),
            client_email=request.form.get('client_email', '').strip(),
            location=request.form.get('location', '').strip(),
            site_address=request.form.get('site_address', '').strip(),
            contract_value=request.form.get('contract_value') or None,
            total_budget=request.form.get('total_budget') or None,
            conservation_type=request.form.get('conservation_type', '').strip(),
            monument_category=request.form.get('monument_category', '').strip(),
            supervising_authority=request.form.get('supervising_authority', '').strip(),
            manager_id=request.form.get('manager_id') or None,
            status='planning',
            notes=request.form.get('notes', '').strip(),
        )
        sd = request.form.get('start_date')
        if sd: p.start_date = datetime.strptime(sd, '%Y-%m-%d').date()
        ed = request.form.get('end_date')
        if ed: p.end_date = datetime.strptime(ed, '%Y-%m-%d').date()
        db.session.add(p)
        db.session.commit()
        flash(f'Έργο {p.code} δημιουργήθηκε.', 'success')
        return redirect(url_for('projects.detail', id=p.id))
    return render_template('projects/new.html', tenders=tenders, users=users)


@projects_bp.route('/<int:id>')
@login_required
def detail(id):
    p = Project.query.get_or_404(id)
    phases = ProjectPhase.query.filter_by(project_id=id).order_by(ProjectPhase.order_num).all()
    logs = ProjectLog.query.filter_by(project_id=id).order_by(ProjectLog.log_date.desc()).limit(20).all()
    team = ProjectTeamMember.query.filter_by(project_id=id).all()
    invoices = Invoice.query.filter_by(project_id=id).order_by(Invoice.invoice_date.desc()).all()
    employees_all = Employee.query.filter_by(status='active').order_by(Employee.last_name).all()
    events = ProjectEvent.query.filter_by(project_id=id).order_by(ProjectEvent.start_date).all()
    requests = MaterialRequest.query.filter_by(project_id=id).order_by(MaterialRequest.created_at.desc()).all()
    today = date.today()
    return render_template('projects/detail.html', project=p, phases=phases,
                           logs=logs, team=team, invoices=invoices, employees_all=employees_all,
                           events=events, material_requests=requests, today=today)


@projects_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    p = Project.query.get_or_404(id)
    users = User.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        p.title = request.form['title'].strip()
        p.description = request.form.get('description', '').strip()
        p.client_name = request.form.get('client_name', '').strip()
        p.client_contact = request.form.get('client_contact', '').strip()
        p.client_email = request.form.get('client_email', '').strip()
        p.location = request.form.get('location', '').strip()
        p.contract_value = request.form.get('contract_value') or None
        p.total_budget = request.form.get('total_budget') or None
        p.status = request.form.get('status', p.status)
        p.progress_pct = request.form.get('progress_pct', p.progress_pct)
        p.conservation_type = request.form.get('conservation_type', '').strip()
        p.supervising_authority = request.form.get('supervising_authority', '').strip()
        p.manager_id = request.form.get('manager_id') or None
        p.notes = request.form.get('notes', '').strip()
        sd = request.form.get('start_date')
        if sd: p.start_date = datetime.strptime(sd, '%Y-%m-%d').date()
        ed = request.form.get('end_date')
        if ed: p.end_date = datetime.strptime(ed, '%Y-%m-%d').date()
        db.session.commit()
        flash('Το έργο ενημερώθηκε.', 'success')
        return redirect(url_for('projects.detail', id=id))
    return render_template('projects/edit.html', project=p, users=users)


@projects_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα διαγραφής έργου.', 'danger')
        return redirect(url_for('projects.detail', id=id))
    p = Project.query.get_or_404(id)
    title = p.title
    db.session.delete(p)
    db.session.commit()
    flash(f'Το έργο "{title}" διαγράφηκε.', 'success')
    return redirect(url_for('projects.index'))


# ── Phases ────────────────────────────────────────────────────────────────
@projects_bp.route('/<int:id>/phases/add', methods=['POST'])
@login_required
def add_phase(id):
    p = Project.query.get_or_404(id)
    order = ProjectPhase.query.filter_by(project_id=id).count()
    phase = ProjectPhase(
        project_id=id,
        name=request.form['name'].strip(),
        description=request.form.get('description', '').strip(),
        order_num=order + 1,
        budget=request.form.get('budget') or None,
        status='pending',
    )
    sd = request.form.get('start_date')
    if sd: phase.start_date = datetime.strptime(sd, '%Y-%m-%d').date()
    ed = request.form.get('end_date')
    if ed: phase.end_date = datetime.strptime(ed, '%Y-%m-%d').date()
    db.session.add(phase)
    db.session.commit()
    flash('Φάση προστέθηκε.', 'success')
    return redirect(url_for('projects.detail', id=id))


@projects_bp.route('/phases/<int:phase_id>/status/<string:new_status>', methods=['POST'])
@login_required
def phase_status(phase_id, new_status):
    phase = ProjectPhase.query.get_or_404(phase_id)
    if new_status in ('pending', 'active', 'completed'):
        phase.status = new_status
        db.session.commit()
    return redirect(url_for('projects.detail', id=phase.project_id))


# ── Daily Log ─────────────────────────────────────────────────────────────
@projects_bp.route('/<int:id>/logs/add', methods=['POST'])
@login_required
def add_log(id):
    log = ProjectLog(
        project_id=id,
        log_date=datetime.strptime(request.form['log_date'], '%Y-%m-%d').date(),
        description=request.form['description'].strip(),
        author_id=current_user.id,
        weather=request.form.get('weather', '').strip(),
        workers_count=request.form.get('workers_count') or None,
        hours_worked=request.form.get('hours_worked') or None,
    )
    db.session.add(log)
    db.session.commit()
    flash('Καταχώρηση ημερολογίου αποθηκεύτηκε.', 'success')
    return redirect(url_for('projects.detail', id=id))


# ── Team ──────────────────────────────────────────────────────────────────
@projects_bp.route('/<int:id>/team/add', methods=['POST'])
@login_required
def add_team_member(id):
    member = ProjectTeamMember(
        project_id=id,
        employee_id=request.form['employee_id'],
        role=request.form.get('role', '').strip(),
        daily_rate=request.form.get('daily_rate') or None,
    )
    sd = request.form.get('start_date')
    if sd: member.start_date = datetime.strptime(sd, '%Y-%m-%d').date()
    db.session.add(member)
    db.session.commit()
    flash('Μέλος συνεργείου προστέθηκε.', 'success')
    return redirect(url_for('projects.detail', id=id))


@projects_bp.route('/team/<int:member_id>/remove', methods=['POST'])
@login_required
def remove_team_member(member_id):
    m = ProjectTeamMember.query.get_or_404(member_id)
    pid = m.project_id
    db.session.delete(m)
    db.session.commit()
    flash('Αφαιρέθηκε από το συνεργείο.', 'success')
    return redirect(url_for('projects.detail', id=pid))


@projects_bp.route('/<int:id>/chat', methods=['POST'])
@login_required
def send_message(id):
    project = Project.query.get_or_404(id)
    text = request.form.get('message', '').strip()
    if text:
        msg = ProjectMessage(project_id=project.id, user_id=current_user.id, message=text)
        db.session.add(msg)
        db.session.commit()
    return redirect(url_for('projects.detail', id=id) + '#chat')


# ── Project Events / Calendar ─────────────────────────────────────────────

EVENT_COLORS = {
    'scaffolding': '#6f42c1', 'closure': '#dc3545',
    'milestone': '#c9a84c', 'inspection': '#0dcaf0',
    'delivery': '#198754', 'meeting': '#0d6efd', 'other': '#6c757d'
}


@projects_bp.route('/<int:id>/events/add', methods=['POST'])
@login_required
def add_event(id):
    Project.query.get_or_404(id)
    event_type = request.form.get('event_type', 'other')
    ev = ProjectEvent(
        project_id=id,
        title=request.form['title'].strip(),
        event_type=event_type,
        description=request.form.get('description', '').strip(),
        milestone_target_pct=request.form.get('milestone_target_pct') or None,
        color=EVENT_COLORS.get(event_type, '#6c757d'),
        created_by_id=current_user.id,
    )
    sd = request.form.get('start_date')
    if sd: ev.start_date = datetime.strptime(sd, '%Y-%m-%d').date()
    else: ev.start_date = date.today()
    ed = request.form.get('end_date')
    if ed: ev.end_date = datetime.strptime(ed, '%Y-%m-%d').date()
    db.session.add(ev)
    db.session.commit()
    flash('Συμβάν προστέθηκε στο ημερολόγιο.', 'success')
    return redirect(url_for('projects.detail', id=id) + '#calendar')


@projects_bp.route('/events/<int:event_id>/toggle', methods=['POST'])
@login_required
def toggle_event(event_id):
    ev = ProjectEvent.query.get_or_404(event_id)
    ev.achieved = not ev.achieved
    db.session.commit()
    flash(f'Συμβάν {"επιτεύχθηκε ✓" if ev.achieved else "αναιρέθηκε"}.', 'success')
    return redirect(url_for('projects.detail', id=ev.project_id) + '#calendar')


@projects_bp.route('/events/<int:event_id>/delete', methods=['POST'])
@login_required
def delete_event(event_id):
    ev = ProjectEvent.query.get_or_404(event_id)
    pid = ev.project_id
    db.session.delete(ev)
    db.session.commit()
    flash('Συμβάν διαγράφηκε.', 'success')
    return redirect(url_for('projects.detail', id=pid) + '#calendar')


@projects_bp.route('/<int:id>/events.json')
@login_required
def events_json(id):
    """FullCalendar-compatible JSON feed."""
    events = ProjectEvent.query.filter_by(project_id=id).all()
    data = []
    for ev in events:
        data.append({
            'id': ev.id,
            'title': f'{"✓ " if ev.achieved else ""}{ev.title}',
            'start': ev.start_date.isoformat(),
            'end': ev.end_date.isoformat() if ev.end_date else None,
            'color': ev.type_color,
            'extendedProps': {
                'type': ev.type_label,
                'description': ev.description or '',
                'achieved': ev.achieved,
            }
        })
    return jsonify(data)


# ── Project Study (Admin Only) ────────────────────────────────────────────

@projects_bp.route('/<int:id>/study/upload', methods=['POST'])
@login_required
def upload_study(id):
    if current_user.role not in ('admin', 'manager'):
        flash('Μόνο διαχειριστές μπορούν να ανεβάσουν τη μελέτη.', 'danger')
        return redirect(url_for('projects.detail', id=id))
    p = Project.query.get_or_404(id)
    file = request.files.get('study_file')
    if not file or not file.filename:
        flash('Επιλέξτε αρχείο.', 'warning')
        return redirect(url_for('projects.detail', id=id))
    fname = secure_filename(f"study_{p.code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'studies')
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, fname))
    p.study_file_path = f'studies/{fname}'
    p.study_file_name = file.filename
    db.session.commit()
    flash('Μελέτη εργου ανέβηκε.', 'success')
    return redirect(url_for('projects.detail', id=id))


@projects_bp.route('/<int:id>/study/view')
@login_required
def view_study(id):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε πρόσβαση στη μελέτη.', 'danger')
        return redirect(url_for('projects.detail', id=id))
    p = Project.query.get_or_404(id)
    if not p.study_file_path:
        flash('Δεν υπάρχει μελέτη.', 'warning')
        return redirect(url_for('projects.detail', id=id))
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], p.study_file_path)


# ── Material Requests (Αιτήσεις Αναλωσίμων) ──────────────────────────────

@projects_bp.route('/<int:id>/requests/new', methods=['POST'])
@login_required
def new_material_request(id):
    Project.query.get_or_404(id)
    req = MaterialRequest(
        project_id=id,
        requested_by_id=current_user.id,
        request_type=request.form.get('request_type', 'materials'),
        title=request.form['title'].strip(),
        description=request.form.get('description', '').strip(),
        quantity=request.form.get('quantity', '').strip(),
        urgency=request.form.get('urgency', 'normal'),
    )
    db.session.add(req)
    db.session.commit()

    # Notify all admin/manager users
    from models import Notification
    admins = User.query.filter(User.role.in_(['admin', 'manager']), User.is_active == True).all()
    for admin in admins:
        n = Notification(
            user_id=admin.id,
            title=f'Αίτηση: {req.title}',
            message=f'{current_user.full_name} ζητά {req.request_type} για έργο #{id}. Επείγον: {req.urgency_label}',
            link=f'/projects/{id}#requests',
            icon='bi-box-seam',
        )
        db.session.add(n)
    db.session.commit()
    flash('Η αίτηση υποβλήθηκε.', 'success')
    return redirect(url_for('projects.detail', id=id) + '#requests')


@projects_bp.route('/requests/<int:req_id>/review', methods=['POST'])
@login_required
def review_material_request(req_id):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε πρόσβαση.', 'danger')
        return redirect(url_for('dashboard.index'))
    req = MaterialRequest.query.get_or_404(req_id)
    action = request.form.get('action', 'approved')
    req.status = action
    req.reviewer_id = current_user.id
    req.reviewer_notes = request.form.get('reviewer_notes', '').strip()
    req.reviewed_at = datetime.utcnow()
    db.session.commit()
    labels = {'approved': 'εγκρίθηκε', 'rejected': 'απορρίφθηκε', 'fulfilled': 'εκτελέστηκε'}
    flash(f'Αίτηση {labels.get(action, action)}.', 'success')
    return redirect(url_for('projects.detail', id=req.project_id) + '#requests')


# ── PROJECT PAYMENT SCHEDULE ────────────────────────────────────────────────

@projects_bp.route('/<int:id>/payments/new', methods=['POST'])
@login_required
def new_project_payment(id):
    project = Project.query.get_or_404(id)
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('projects.detail', id=id))
    try:
        pp = ProjectPayment(
            project_id=id,
            title=request.form['title'].strip(),
            milestone=request.form.get('milestone', '').strip(),
            amount_expected=float(request.form['amount_expected']),
            notes=request.form.get('notes', '').strip(),
        )
        dd = request.form.get('due_date')
        if dd: pp.due_date = datetime.strptime(dd, '%Y-%m-%d').date()
        db.session.add(pp)
        db.session.commit()
        flash(f'Δόση "{pp.title}" προστέθηκε.', 'success')
    except Exception as e:
        flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('projects.detail', id=id) + '#payments')


@projects_bp.route('/payments/<int:pp_id>/pay', methods=['POST'])
@login_required
def pay_project_payment(pp_id):
    pp = ProjectPayment.query.get_or_404(pp_id)
    try:
        amount = float(request.form['amount_paid'])
        pp.amount_paid = amount
        pp.paid_date = date.today()
        expected = float(pp.amount_expected)
        pp.status = 'paid' if amount >= expected - 0.01 else 'partial'
        # Link invoice if provided
        inv_id = request.form.get('invoice_id')
        if inv_id:
            pp.invoice_id = int(inv_id)
        db.session.commit()
        flash(f'Πληρωμή {amount:.2f}€ καταχωρήθηκε για "{pp.title}".', 'success')
    except Exception as e:
        flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('projects.detail', id=pp.project_id) + '#payments')


@projects_bp.route('/payments/<int:pp_id>/delete', methods=['POST'])
@login_required
def delete_project_payment(pp_id):
    pp = ProjectPayment.query.get_or_404(pp_id)
    project_id = pp.project_id
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('projects.detail', id=project_id))
    db.session.delete(pp)
    db.session.commit()
    flash('Δόση διαγράφηκε.', 'success')
    return redirect(url_for('projects.detail', id=project_id) + '#payments')


# ── PHOTO ARCHIVE ─────────────────────────────────────────────────────────────

@projects_bp.route('/<int:id>/photos')
@login_required
def photos(id):
    project = Project.query.get_or_404(id)
    phase_filter = request.args.get('phase_id', '')
    type_filter  = request.args.get('photo_type', '')
    q = project.photos
    if phase_filter: q = q.filter_by(phase_id=int(phase_filter))
    if type_filter:  q = q.filter_by(photo_type=type_filter)
    all_photos = q.order_by(ProjectPhoto.created_at.desc()).all()
    phases = project.phases.all()
    return render_template('projects/photos.html', project=project, photos=all_photos,
                           phases=phases, phase_filter=phase_filter, type_filter=type_filter)


@projects_bp.route('/<int:id>/photos/upload', methods=['POST'])
@login_required
def upload_photo(id):
    project = Project.query.get_or_404(id)
    files = request.files.getlist('photos')
    if not files or not files[0].filename:
        flash('Επιλέξτε τουλάχιστον μία φωτογραφία.', 'warning')
        return redirect(url_for('projects.photos', id=id))

    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'project_photos', str(id))
    os.makedirs(upload_dir, exist_ok=True)

    photo_type  = request.form.get('photo_type', 'during')
    phase_id    = request.form.get('phase_id') or None
    description = request.form.get('description', '').strip()
    taken_at_str = request.form.get('taken_at')
    taken_at    = datetime.strptime(taken_at_str, '%Y-%m-%d').date() if taken_at_str else date.today()

    count = 0
    for f in files:
        if not f.filename: continue
        ext = f.filename.rsplit('.', 1)[-1].lower()
        if ext not in ('jpg', 'jpeg', 'png', 'webp', 'heic'):
            continue
        fname = secure_filename(f'p{id}_{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}_{f.filename}')
        rel_path = f'project_photos/{id}/{fname}'
        f.save(os.path.join(current_app.config['UPLOAD_FOLDER'], rel_path))
        photo = ProjectPhoto(
            project_id=id, phase_id=phase_id, file_path=rel_path, file_name=f.filename,
            photo_type=photo_type, description=description, taken_at=taken_at,
            uploaded_by_id=current_user.id,
        )
        db.session.add(photo)
        count += 1

    db.session.commit()
    flash(f'{count} φωτογραφία(ες) ανέβηκαν.', 'success')
    return redirect(url_for('projects.photos', id=id))


@projects_bp.route('/photos/<int:photo_id>/delete', methods=['POST'])
@login_required
def delete_photo(photo_id):
    photo = ProjectPhoto.query.get_or_404(photo_id)
    project_id = photo.project_id
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('projects.photos', id=project_id))
    full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], photo.file_path)
    if os.path.exists(full_path):
        os.remove(full_path)
    db.session.delete(photo)
    db.session.commit()
    flash('Φωτογραφία διαγράφηκε.', 'success')
    return redirect(url_for('projects.photos', id=project_id))
