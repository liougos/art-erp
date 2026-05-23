from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, date
from models import db, DesignProject, DesignRevision, Project, Employee, Subcontractor, User
import os

design_bp = Blueprint('design', __name__)

DESIGN_TYPES = [
    ('architectural', 'Αρχιτεκτονική'),
    ('structural',    'Στατική'),
    ('electrical',    'Ηλεκτρολογική'),
    ('mechanical',    'Μηχανολογική'),
    ('interior',      'Εσωτερικός Χώρος'),
    ('color_scheme',  'Χρωματολόγιο'),
    ('other',         'Άλλο'),
]

STATUSES = [
    ('draft',     'Πρόχειρο'),
    ('in_design', 'Σε Εξέλιξη'),
    ('in_review', 'Προς Έγκριση'),
    ('approved',  'Εγκρίθηκε'),
    ('rejected',  'Απορρίφθηκε'),
    ('final',     'Οριστικοποιήθηκε'),
]

PRIORITIES = [
    ('low',    'Χαμηλή'),
    ('normal', 'Κανονική'),
    ('high',   'Υψηλή'),
    ('urgent', 'Επείγον'),
]


@design_bp.route('/')
@login_required
def index():
    status_filter = request.args.get('status', '')
    project_filter = request.args.get('project_id', '')
    type_filter = request.args.get('design_type', '')

    q = DesignProject.query
    if status_filter:
        q = q.filter_by(status=status_filter)
    if project_filter:
        q = q.filter_by(project_id=int(project_filter))
    if type_filter:
        q = q.filter_by(design_type=type_filter)

    designs  = q.order_by(DesignProject.created_at.desc()).all()
    projects = Project.query.order_by(Project.code).all()

    # Stats
    total   = DesignProject.query.count()
    pending = DesignProject.query.filter(DesignProject.status.in_(['draft','in_design','in_review'])).count()
    approved = DesignProject.query.filter_by(status='approved').count()
    final   = DesignProject.query.filter_by(status='final').count()

    return render_template('design/index.html',
                           designs=designs, projects=projects,
                           design_types=DESIGN_TYPES, statuses=STATUSES, priorities=PRIORITIES,
                           status_filter=status_filter, project_filter=project_filter,
                           type_filter=type_filter,
                           total=total, pending=pending, approved=approved, final=final,
                           today=date.today())


@design_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    if request.method == 'POST':
        try:
            dp = DesignProject(
                title=request.form.get('title', '').strip(),
                design_type=request.form.get('design_type', 'architectural'),
                description=request.form.get('description', '').strip(),
                client_brief=request.form.get('client_brief', '').strip(),
                status=request.form.get('status', 'draft'),
                priority=request.form.get('priority', 'normal'),
                notes=request.form.get('notes', '').strip(),
                created_by_id=current_user.id,
            )
            pid = request.form.get('project_id')
            did = request.form.get('designer_id')
            sid = request.form.get('assigned_sub_id')
            dl  = request.form.get('deadline')
            bud = request.form.get('budget')

            if pid: dp.project_id    = int(pid)
            if did: dp.designer_id   = int(did)
            if sid: dp.assigned_sub_id = int(sid)
            if dl:  dp.deadline      = datetime.strptime(dl, '%Y-%m-%d').date()
            if bud: dp.budget        = float(bud)

            db.session.add(dp)
            db.session.commit()
            flash(f'Μελέτη "{dp.title}" δημιουργήθηκε.', 'success')
            return redirect(url_for('design.detail', id=dp.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Σφάλμα: {e}', 'danger')

    projects  = Project.query.order_by(Project.code).all()
    employees = Employee.query.filter_by(status='active').order_by(Employee.last_name).all()
    subs      = Subcontractor.query.filter_by(is_active=True).order_by(Subcontractor.company_name).all()
    return render_template('design/new.html',
                           projects=projects, employees=employees, subs=subs,
                           design_types=DESIGN_TYPES, statuses=STATUSES, priorities=PRIORITIES,
                           today=date.today())


@design_bp.route('/<int:id>')
@login_required
def detail(id):
    dp = DesignProject.query.get_or_404(id)
    revisions = dp.revisions.order_by(DesignRevision.version_number.desc()).all()
    employees = Employee.query.filter_by(status='active').order_by(Employee.last_name).all()
    subs      = Subcontractor.query.filter_by(is_active=True).order_by(Subcontractor.company_name).all()
    projects  = Project.query.order_by(Project.code).all()
    return render_template('design/detail.html',
                           dp=dp, revisions=revisions,
                           employees=employees, subs=subs, projects=projects,
                           design_types=DESIGN_TYPES, statuses=STATUSES, priorities=PRIORITIES,
                           today=date.today())


@design_bp.route('/<int:id>/edit', methods=['POST'])
@login_required
def edit(id):
    dp = DesignProject.query.get_or_404(id)
    try:
        dp.title       = request.form.get('title', dp.title).strip()
        dp.design_type = request.form.get('design_type', dp.design_type)
        dp.status      = request.form.get('status', dp.status)
        dp.priority    = request.form.get('priority', dp.priority)
        dp.description = request.form.get('description', '').strip()
        dp.client_brief = request.form.get('client_brief', '').strip()
        dp.notes       = request.form.get('notes', '').strip()

        pid = request.form.get('project_id')
        did = request.form.get('designer_id')
        sid = request.form.get('assigned_sub_id')
        dl  = request.form.get('deadline')
        bud = request.form.get('budget')
        act = request.form.get('actual_cost')

        dp.project_id    = int(pid) if pid else None
        dp.designer_id   = int(did) if did else None
        dp.assigned_sub_id = int(sid) if sid else None
        dp.deadline      = datetime.strptime(dl, '%Y-%m-%d').date() if dl else None
        if bud: dp.budget = float(bud)
        if act: dp.actual_cost = float(act)

        # Set approved_date if transitioning to approved/final
        if dp.status in ('approved', 'final') and not dp.approved_date:
            dp.approved_date = date.today()

        dp.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Μελέτη ενημερώθηκε.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('design.detail', id=id))


@design_bp.route('/<int:id>/revision/new', methods=['POST'])
@login_required
def new_revision(id):
    dp = DesignProject.query.get_or_404(id)
    try:
        # Auto-increment version number
        last = dp.revisions.order_by(DesignRevision.version_number.desc()).first()
        next_ver = (last.version_number + 1) if last else 1

        rev = DesignRevision(
            design_id=dp.id,
            version_number=next_ver,
            title=request.form.get('title', f'Έκδοση {next_ver}').strip(),
            description=request.form.get('description', '').strip(),
            submitted_by_id=current_user.id,
            status='pending',
        )

        # Handle file upload
        f = request.files.get('revision_file')
        if f and f.filename:
            upload_dir = os.path.join('static', 'uploads', 'design', str(dp.id))
            os.makedirs(upload_dir, exist_ok=True)
            safe_name = f.filename.replace(' ', '_')
            fpath = os.path.join(upload_dir, safe_name)
            f.save(fpath)
            rev.file_path = fpath
            rev.file_name = f.filename

        db.session.add(rev)
        # Advance design to in_review if still earlier
        if dp.status in ('draft', 'in_design'):
            dp.status = 'in_review'
        db.session.commit()
        flash(f'Έκδοση {next_ver} υποβλήθηκε.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('design.detail', id=id))


@design_bp.route('/revision/<int:rev_id>/approve', methods=['POST'])
@login_required
def approve_revision(rev_id):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('design.index'))
    rev = DesignRevision.query.get_or_404(rev_id)
    rev.status = 'approved'
    rev.reviewed_by_id = current_user.id
    rev.review_notes = request.form.get('review_notes', '').strip()
    rev.design.status = 'approved'
    rev.design.approved_date = date.today()
    db.session.commit()
    flash('Έκδοση εγκρίθηκε.', 'success')
    return redirect(url_for('design.detail', id=rev.design_id))


@design_bp.route('/revision/<int:rev_id>/reject', methods=['POST'])
@login_required
def reject_revision(rev_id):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('design.index'))
    rev = DesignRevision.query.get_or_404(rev_id)
    rev.status = 'rejected'
    rev.reviewed_by_id = current_user.id
    rev.review_notes = request.form.get('review_notes', '').strip()
    rev.design.status = 'in_design'   # send back for redesign
    db.session.commit()
    flash('Έκδοση απορρίφθηκε — μελέτη επιστράφηκε σε εξέλιξη.', 'warning')
    return redirect(url_for('design.detail', id=rev.design_id))
