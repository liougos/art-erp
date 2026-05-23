import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_required, current_user
from datetime import datetime, date
from werkzeug.utils import secure_filename
from models import (db, Subcontractor, SubcontractorContract, SubcontractorWorkLog,
                    SubcontractorInvoice, SubcontractorDocument, SubcontractorPersonnel,
                    SubcontractorMeasurement, ProjectSharedDocument,
                    Project, ProjectPhase, Employee, User)

subcontractors_bp = Blueprint('subcontractors', __name__)

SPECIALTIES = [
    ('conservator',       'Συντηρητής Αρχαιοτήτων'),
    ('conservator_paper', 'Συντηρητής Χαρτιού / Βιβλίων'),
    ('conservator_wood',  'Συντηρητής Ξύλου / Επίπλων'),
    ('conservator_stone', 'Συντηρητής Λίθου / Τοιχογραφιών'),
    ('conservator_metal', 'Συντηρητής Μετάλλων'),
    ('showcases',         'Προθήκες / Εξοπλισμός Έκθεσης'),
    ('lighting',          'Φωτισμός Χώρων'),
    ('electrical',        'Ηλεκτρολογικά'),
    ('cleaning',          'Καθαρισμός'),
    ('transport',         'Μεταφορές / Συσκευασία'),
    ('security',          'Συστήματα Ασφαλείας'),
    ('other',             'Άλλο'),
]


# ── ΥΠΕΡΓΟΛΑΒΟΙ (ADMIN) ──────────────────────────────────────────────────────

@subcontractors_bp.route('/')
@login_required
def index():
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε πρόσβαση.', 'danger')
        return redirect(url_for('dashboard.index'))
    specialty = request.args.get('specialty', '')
    q = Subcontractor.query.filter_by(is_active=True)
    if specialty:
        q = q.filter_by(specialty=specialty)
    subs = q.order_by(Subcontractor.company_name).all()
    return render_template('subcontractors/index.html',
                           subs=subs, specialties=SPECIALTIES, specialty=specialty, today=date.today())


@subcontractors_bp.route('/new', methods=['POST'])
@login_required
def new():
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('subcontractors.index'))
    try:
        sub = Subcontractor(
            company_name=request.form['company_name'].strip(),
            afm=request.form.get('afm', '').strip(),
            contact_name=request.form.get('contact_name', '').strip(),
            phone=request.form.get('phone', '').strip(),
            email=request.form.get('email', '').strip(),
            address=request.form.get('address', '').strip(),
            specialty=request.form.get('specialty', 'other'),
            insurance_number=request.form.get('insurance_number', '').strip(),
            notes=request.form.get('notes', '').strip(),
        )
        ed = request.form.get('insurance_expiry')
        if ed: sub.insurance_expiry = datetime.strptime(ed, '%Y-%m-%d').date()
        # Portal credentials
        username = request.form.get('portal_username', '').strip()
        password = request.form.get('portal_password', '').strip()
        if username and password:
            sub.portal_username = username
            sub.set_portal_password(password)
        db.session.add(sub)
        db.session.commit()
        flash(f'Υπεργολάβος "{sub.company_name}" προστέθηκε.', 'success')
    except Exception as e:
        flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('subcontractors.index'))


@subcontractors_bp.route('/<int:id>')
@login_required
def detail(id):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε πρόσβαση.', 'danger')
        return redirect(url_for('dashboard.index'))
    sub = Subcontractor.query.get_or_404(id)
    contracts = sub.contracts.order_by(SubcontractorContract.created_at.desc()).all()
    projects  = Project.query.filter(Project.status.in_(['active', 'planning'])).order_by(Project.code).all()
    return render_template('subcontractors/detail.html',
                           sub=sub, contracts=contracts, projects=projects,
                           specialties=SPECIALTIES, today=date.today())


@subcontractors_bp.route('/<int:id>/edit', methods=['POST'])
@login_required
def edit(id):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('subcontractors.index'))
    sub = Subcontractor.query.get_or_404(id)
    sub.company_name    = request.form['company_name'].strip()
    sub.afm             = request.form.get('afm', '').strip()
    sub.contact_name    = request.form.get('contact_name', '').strip()
    sub.phone           = request.form.get('phone', '').strip()
    sub.email           = request.form.get('email', '').strip()
    sub.address         = request.form.get('address', '').strip()
    sub.specialty       = request.form.get('specialty', sub.specialty)
    sub.insurance_number = request.form.get('insurance_number', '').strip()
    sub.rating          = int(request.form.get('rating', sub.rating or 3))
    sub.notes           = request.form.get('notes', '').strip()
    sub.is_active       = request.form.get('is_active') == '1'
    ed = request.form.get('insurance_expiry')
    if ed: sub.insurance_expiry = datetime.strptime(ed, '%Y-%m-%d').date()
    # Portal credentials update
    username = request.form.get('portal_username', '').strip()
    password = request.form.get('portal_password', '').strip()
    if username: sub.portal_username = username
    if password: sub.set_portal_password(password)
    db.session.commit()
    flash('Στοιχεία υπεργολάβου ενημερώθηκαν.', 'success')
    return redirect(url_for('subcontractors.detail', id=id))


# ── ΣΥΜΒΑΣΕΙΣ ──────────────────────────────────────────────────────────────

@subcontractors_bp.route('/<int:sub_id>/contract/new', methods=['POST'])
@login_required
def new_contract(sub_id):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('subcontractors.detail', id=sub_id))
    try:
        c = SubcontractorContract(
            subcontractor_id=sub_id,
            title=request.form['title'].strip(),
            scope_of_work=request.form.get('scope_of_work', '').strip(),
            contract_value=float(request.form.get('contract_value', 0) or 0),
            payment_terms=request.form.get('payment_terms', '').strip(),
            project_id=request.form.get('project_id') or None,
            notes=request.form.get('notes', '').strip(),
            status='draft',
        )
        sd = request.form.get('start_date')
        ed = request.form.get('end_date')
        if sd: c.start_date = datetime.strptime(sd, '%Y-%m-%d').date()
        if ed: c.end_date   = datetime.strptime(ed, '%Y-%m-%d').date()
        db.session.add(c)
        db.session.commit()
        flash(f'Σύμβαση "{c.title}" δημιουργήθηκε.', 'success')
    except Exception as e:
        flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('subcontractors.detail', id=sub_id))


@subcontractors_bp.route('/contract/<int:id>/status', methods=['POST'])
@login_required
def contract_status(id):
    c = SubcontractorContract.query.get_or_404(id)
    new_status = request.form.get('status')
    if new_status in ('draft', 'signed', 'active', 'completed', 'terminated'):
        c.status = new_status
        db.session.commit()
        flash(f'Κατάσταση σύμβασης: {c.status_label}', 'success')
    return redirect(url_for('subcontractors.detail', id=c.subcontractor_id))


@subcontractors_bp.route('/contract/<int:id>/invoice/new', methods=['POST'])
@login_required
def new_invoice(id):
    c = SubcontractorContract.query.get_or_404(id)
    try:
        net = float(request.form.get('amount_net', 0) or 0)
        vat_rate = float(request.form.get('vat_rate', 24) or 24)
        vat_amt  = round(net * vat_rate / 100, 2)
        inv = SubcontractorInvoice(
            contract_id=id,
            invoice_number=request.form.get('invoice_number', '').strip(),
            amount_net=net, vat_rate=vat_rate, vat_amount=vat_amt,
            total_amount=round(net + vat_amt, 2),
            notes=request.form.get('notes', '').strip(),
        )
        id_str = request.form.get('invoice_date')
        pf     = request.form.get('period_from')
        pt     = request.form.get('period_to')
        if id_str: inv.invoice_date = datetime.strptime(id_str, '%Y-%m-%d').date()
        if pf:     inv.period_from  = datetime.strptime(pf, '%Y-%m-%d').date()
        if pt:     inv.period_to    = datetime.strptime(pt, '%Y-%m-%d').date()
        # File upload
        f = request.files.get('invoice_file')
        if f and f.filename:
            upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'subcontractor_invoices')
            os.makedirs(upload_dir, exist_ok=True)
            fname = secure_filename(f'sub{id}_{datetime.now().strftime("%Y%m%d%H%M%S")}_{f.filename}')
            f.save(os.path.join(upload_dir, fname))
            inv.file_path = f'subcontractor_invoices/{fname}'
        db.session.add(inv)
        db.session.commit()
        flash('Τιμολόγιο υπεργολάβου καταχωρήθηκε.', 'success')
    except Exception as e:
        flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('subcontractors.detail', id=c.subcontractor_id))


@subcontractors_bp.route('/invoice/<int:id>/pay', methods=['POST'])
@login_required
def pay_invoice(id):
    inv = SubcontractorInvoice.query.get_or_404(id)
    inv.status    = 'paid'
    inv.paid_date = date.today()
    db.session.commit()
    flash('Τιμολόγιο σημάνθηκε ως πληρωμένο.', 'success')
    return redirect(url_for('subcontractors.detail', id=inv.contract.subcontractor_id))


# ── WORK LOGS (admin view) ──────────────────────────────────────────────────

@subcontractors_bp.route('/worklogs')
@login_required
def all_worklogs():
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε πρόσβαση.', 'danger')
        return redirect(url_for('dashboard.index'))
    pending = SubcontractorWorkLog.query.filter_by(status='pending').order_by(
        SubcontractorWorkLog.log_date.desc()).all()
    return render_template('subcontractors/worklogs.html', logs=pending, today=date.today())


@subcontractors_bp.route('/worklog/<int:id>/approve', methods=['POST'])
@login_required
def approve_worklog(id):
    log = SubcontractorWorkLog.query.get_or_404(id)
    log.status        = 'approved'
    log.reviewed_by_id = current_user.id
    log.reviewed_at   = datetime.utcnow()
    db.session.commit()
    flash('Αναφορά εγκρίθηκε.', 'success')
    return redirect(url_for('subcontractors.all_worklogs'))


@subcontractors_bp.route('/worklog/<int:id>/reject', methods=['POST'])
@login_required
def reject_worklog(id):
    log = SubcontractorWorkLog.query.get_or_404(id)
    log.status        = 'rejected'
    log.reviewed_by_id = current_user.id
    log.reviewed_at   = datetime.utcnow()
    db.session.commit()
    flash('Αναφορά απορρίφθηκε.', 'warning')
    return redirect(url_for('subcontractors.all_worklogs'))


# ── SUBCONTRACTOR PORTAL ────────────────────────────────────────────────────

@subcontractors_bp.route('/portal')
def portal_dashboard():
    sub_id = session.get('sub_portal_id')
    if not sub_id:
        return redirect(url_for('subcontractors.portal_login'))
    sub = Subcontractor.query.get_or_404(sub_id)
    active_contracts = sub.contracts.filter(
        SubcontractorContract.status.in_(['signed', 'active'])
    ).order_by(SubcontractorContract.start_date).all()
    pending_logs = SubcontractorWorkLog.query.join(SubcontractorContract).filter(
        SubcontractorContract.subcontractor_id == sub_id,
        SubcontractorWorkLog.status == 'pending'
    ).count()
    return render_template('subcontractors/portal/dashboard.html',
                           sub=sub, active_contracts=active_contracts,
                           pending_logs=pending_logs, today=date.today())


@subcontractors_bp.route('/portal/login', methods=['GET', 'POST'])
def portal_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        sub = Subcontractor.query.filter_by(portal_username=username, is_active=True).first()
        if sub and sub.portal_password_hash and sub.check_portal_password(password):
            session['sub_portal_id'] = sub.id
            flash(f'Καλωσήρθατε, {sub.company_name}!', 'success')
            return redirect(url_for('subcontractors.portal_dashboard'))
        flash('Λάθος στοιχεία σύνδεσης.', 'danger')
    return render_template('subcontractors/portal/login.html')


@subcontractors_bp.route('/portal/logout')
def portal_logout():
    session.pop('sub_portal_id', None)
    return redirect(url_for('subcontractors.portal_login'))


@subcontractors_bp.route('/portal/worklog/new', methods=['POST'])
def portal_new_worklog():
    sub_id = session.get('sub_portal_id')
    if not sub_id:
        return redirect(url_for('subcontractors.portal_login'))
    try:
        log = SubcontractorWorkLog(
            contract_id=int(request.form['contract_id']),
            work_description=request.form['work_description'].strip(),
            workers_count=int(request.form.get('workers_count', 1) or 1),
            hours_worked=float(request.form.get('hours_worked', 8) or 8),
            completion_pct=int(request.form.get('completion_pct', 0) or 0),
            issues=request.form.get('issues', '').strip(),
        )
        ld = request.form.get('log_date')
        if ld: log.log_date = datetime.strptime(ld, '%Y-%m-%d').date()
        db.session.add(log)
        db.session.commit()
        flash('Αναφορά υποβλήθηκε για έγκριση.', 'success')
    except Exception as e:
        flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('subcontractors.portal_dashboard'))


@subcontractors_bp.route('/portal/my-invoices')
def portal_invoices():
    sub_id = session.get('sub_portal_id')
    if not sub_id:
        return redirect(url_for('subcontractors.portal_login'))
    sub = Subcontractor.query.get_or_404(sub_id)
    all_invoices = SubcontractorInvoice.query.join(SubcontractorContract).filter(
        SubcontractorContract.subcontractor_id == sub_id
    ).order_by(SubcontractorInvoice.invoice_date.desc()).all()
    return render_template('subcontractors/portal/invoices.html',
                           sub=sub, invoices=all_invoices, today=date.today())


@subcontractors_bp.route('/portal/my-project')
def portal_project():
    """Υπεργολάβος βλέπει χρονοδιάγραμμα & αναφορές του συνδεδεμένου έργου."""
    sub_id = session.get('sub_portal_id')
    if not sub_id:
        return redirect(url_for('subcontractors.portal_login'))
    sub = Subcontractor.query.get_or_404(sub_id)

    # Gather all projects linked via active contracts
    contracts = sub.contracts.filter(
        SubcontractorContract.status.in_(['signed', 'active'])
    ).all()

    # Get unique projects
    projects = []
    seen = set()
    for c in contracts:
        if c.project and c.project_id not in seen:
            projects.append(c.project)
            seen.add(c.project_id)

    # Selected project (default: first active)
    project_id = request.args.get('project_id', type=int)
    project = None
    phases = []
    reports = []
    if projects:
        project = next((p for p in projects if p.id == project_id), projects[0])
        phases  = project.phases.all() if project else []
        # Last 20 approved daily reports for this project
        from models import DailyReport
        reports = DailyReport.query.filter_by(
            project_id=project.id, status='approved'
        ).order_by(DailyReport.report_date.desc()).limit(20).all()

    return render_template('subcontractors/portal/project.html',
                           sub=sub, contracts=contracts,
                           projects=projects, project=project,
                           phases=phases, reports=reports,
                           today=date.today())


@subcontractors_bp.route('/portal/my-reports')
def portal_reports():
    """Υπεργολάβος βλέπει τις δικές του αναφορές εργασίας (work logs)."""
    sub_id = session.get('sub_portal_id')
    if not sub_id:
        return redirect(url_for('subcontractors.portal_login'))
    sub = Subcontractor.query.get_or_404(sub_id)

    logs = SubcontractorWorkLog.query.join(SubcontractorContract).filter(
        SubcontractorContract.subcontractor_id == sub_id
    ).order_by(SubcontractorWorkLog.log_date.desc()).all()

    return render_template('subcontractors/portal/reports.html',
                           sub=sub, logs=logs, today=date.today())


# ══════════════════════════════════════════════════════════════════════════════
# ΔΙΚΑΙΟΛΟΓΗΤΙΚΑ ΥΠΕΡΓΟΛΑΒΟΥ
# ══════════════════════════════════════════════════════════════════════════════

@subcontractors_bp.route('/<int:id>/documents')
@login_required
def sub_documents(id):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε πρόσβαση.', 'danger')
        return redirect(url_for('dashboard.index'))
    sub  = Subcontractor.query.get_or_404(id)
    docs = sub.documents.all()
    expired  = [d for d in docs if d.expiry_status == 'expired']
    expiring = [d for d in docs if d.expiry_status == 'expiring']
    return render_template('subcontractors/documents.html',
                           sub=sub, docs=docs, expired=expired,
                           expiring=expiring, today=date.today(),
                           doc_types=SubcontractorDocument.DOC_TYPES)


@subcontractors_bp.route('/<int:id>/documents/add', methods=['POST'])
@login_required
def add_sub_document(id):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('subcontractors.sub_documents', id=id))
    sub = Subcontractor.query.get_or_404(id)
    try:
        upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'sub_docs', str(id))
        os.makedirs(upload_dir, exist_ok=True)
        file_path = None
        file_name = None
        f = request.files.get('doc_file')
        if f and f.filename:
            fname = secure_filename(f'{datetime.now().strftime("%Y%m%d%H%M%S")}_{f.filename}')
            f.save(os.path.join(upload_dir, fname))
            file_path = f'sub_docs/{id}/{fname}'
            file_name = f.filename

        doc = SubcontractorDocument(
            subcontractor_id=id,
            doc_type=request.form.get('doc_type', 'other'),
            title=request.form['title'].strip(),
            file_path=file_path,
            file_name=file_name,
            notes=request.form.get('notes', '').strip(),
        )
        id_str = request.form.get('issue_date')
        ex_str = request.form.get('expiry_date')
        if id_str: doc.issue_date  = datetime.strptime(id_str, '%Y-%m-%d').date()
        if ex_str: doc.expiry_date = datetime.strptime(ex_str, '%Y-%m-%d').date()
        db.session.add(doc)
        db.session.commit()
        flash(f'Δικαιολογητικό "{doc.title}" προστέθηκε.', 'success')
    except Exception as e:
        flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('subcontractors.sub_documents', id=id))


@subcontractors_bp.route('/document/<int:doc_id>/delete', methods=['POST'])
@login_required
def delete_sub_document(doc_id):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('subcontractors.index'))
    doc = SubcontractorDocument.query.get_or_404(doc_id)
    sub_id = doc.subcontractor_id
    db.session.delete(doc)
    db.session.commit()
    flash('Δικαιολογητικό διαγράφηκε.', 'success')
    return redirect(url_for('subcontractors.sub_documents', id=sub_id))


# ══════════════════════════════════════════════════════════════════════════════
# ΕΠΙΜΕΤΡΗΣΕΙΣ
# ══════════════════════════════════════════════════════════════════════════════

@subcontractors_bp.route('/contract/<int:cid>/measurements')
@login_required
def measurements(cid):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε πρόσβαση.', 'danger')
        return redirect(url_for('dashboard.index'))
    c    = SubcontractorContract.query.get_or_404(cid)
    meas = c.measurements.order_by(SubcontractorMeasurement.measurement_date.desc()).all()
    phases = ProjectPhase.query.filter_by(project_id=c.project_id).all() if c.project_id else []
    return render_template('subcontractors/measurements.html',
                           contract=c, measurements=meas, phases=phases, today=date.today())


@subcontractors_bp.route('/contract/<int:cid>/measurements/add', methods=['POST'])
@login_required
def add_measurement(cid):
    c = SubcontractorContract.query.get_or_404(cid)
    try:
        qty   = float(request.form.get('quantity', 0) or 0)
        price = float(request.form.get('unit_price', 0) or 0)
        m = SubcontractorMeasurement(
            contract_id=cid,
            phase_id=request.form.get('phase_id') or None,
            title=request.form['title'].strip(),
            description=request.form.get('description', '').strip(),
            quantity=qty,
            unit=request.form.get('unit', 'τ.μ.').strip(),
            unit_price=price,
            total_amount=round(qty * price, 2),
            notes=request.form.get('notes', '').strip(),
            status='pending',
        )
        md = request.form.get('measurement_date')
        if md: m.measurement_date = datetime.strptime(md, '%Y-%m-%d').date()
        db.session.add(m)
        db.session.commit()
        flash(f'Επιμέτρηση "{m.title}" καταχωρήθηκε.', 'success')
    except Exception as e:
        flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('subcontractors.measurements', cid=cid))


@subcontractors_bp.route('/measurement/<int:mid>/approve', methods=['POST'])
@login_required
def approve_measurement(mid):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('subcontractors.index'))
    m = SubcontractorMeasurement.query.get_or_404(mid)
    m.status        = 'approved'
    m.approved_by_id = current_user.id
    m.approved_at   = datetime.utcnow()
    db.session.commit()
    flash(f'Επιμέτρηση εγκρίθηκε ({m.total_amount:.2f}€).', 'success')
    return redirect(url_for('subcontractors.measurements', cid=m.contract_id))


@subcontractors_bp.route('/measurement/<int:mid>/reject', methods=['POST'])
@login_required
def reject_measurement(mid):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('subcontractors.index'))
    m = SubcontractorMeasurement.query.get_or_404(mid)
    m.status           = 'rejected'
    m.rejection_reason = request.form.get('reason', '').strip()
    m.approved_by_id   = current_user.id
    m.approved_at      = datetime.utcnow()
    db.session.commit()
    flash('Επιμέτρηση απορρίφθηκε.', 'warning')
    return redirect(url_for('subcontractors.measurements', cid=m.contract_id))


# ══════════════════════════════════════════════════════════════════════════════
# PORTAL — ΠΡΟΣΩΠΙΚΟ & ΑΔΕΙΕΣ
# ══════════════════════════════════════════════════════════════════════════════

@subcontractors_bp.route('/portal/personnel')
def portal_personnel():
    sub_id = session.get('sub_portal_id')
    if not sub_id:
        return redirect(url_for('subcontractors.portal_login'))
    sub       = Subcontractor.query.get_or_404(sub_id)
    personnel = sub.personnel.all()
    return render_template('subcontractors/portal/personnel.html',
                           sub=sub, personnel=personnel,
                           roles=SubcontractorPersonnel.ROLES, today=date.today())


@subcontractors_bp.route('/portal/personnel/add', methods=['POST'])
def portal_add_personnel():
    sub_id = session.get('sub_portal_id')
    if not sub_id:
        return redirect(url_for('subcontractors.portal_login'))
    try:
        p = SubcontractorPersonnel(
            subcontractor_id=sub_id,
            full_name=request.form['full_name'].strip(),
            role=request.form.get('role', 'technician'),
            license_type=request.form.get('license_type', '').strip(),
            license_number=request.form.get('license_number', '').strip(),
            notes=request.form.get('notes', '').strip(),
        )
        le = request.form.get('license_expiry')
        if le: p.license_expiry = datetime.strptime(le, '%Y-%m-%d').date()

        # Upload license file
        f = request.files.get('license_file')
        if f and f.filename:
            upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'sub_personnel', str(sub_id))
            os.makedirs(upload_dir, exist_ok=True)
            fname = secure_filename(f'{datetime.now().strftime("%Y%m%d%H%M%S")}_{f.filename}')
            f.save(os.path.join(upload_dir, fname))
            p.license_file_path = f'sub_personnel/{sub_id}/{fname}'

        db.session.add(p)
        db.session.commit()
        flash(f'Εργαζόμενος "{p.full_name}" προστέθηκε.', 'success')
    except Exception as e:
        flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('subcontractors.portal_personnel'))


@subcontractors_bp.route('/portal/personnel/<int:pid>/toggle', methods=['POST'])
def portal_toggle_personnel(pid):
    sub_id = session.get('sub_portal_id')
    if not sub_id:
        return redirect(url_for('subcontractors.portal_login'))
    p = SubcontractorPersonnel.query.get_or_404(pid)
    if p.subcontractor_id != sub_id:
        flash('Δεν επιτρέπεται.', 'danger')
        return redirect(url_for('subcontractors.portal_personnel'))
    p.is_active = not p.is_active
    db.session.commit()
    flash(f'{"Ενεργοποιήθηκε" if p.is_active else "Απενεργοποιήθηκε"}: {p.full_name}', 'info')
    return redirect(url_for('subcontractors.portal_personnel'))


# ══════════════════════════════════════════════════════════════════════════════
# PORTAL — ΚΟΙΝΟΧΡΗΣΤΑ ΕΓΓΡΑΦΑ ΕΡΓΟΥ
# ══════════════════════════════════════════════════════════════════════════════

@subcontractors_bp.route('/portal/shared-docs')
def portal_shared_docs():
    sub_id = session.get('sub_portal_id')
    if not sub_id:
        return redirect(url_for('subcontractors.portal_login'))
    sub  = Subcontractor.query.get_or_404(sub_id)
    docs = ProjectSharedDocument.query.filter_by(subcontractor_id=sub_id).order_by(
        ProjectSharedDocument.created_at.desc()).all()
    return render_template('subcontractors/portal/shared_docs.html',
                           sub=sub, docs=docs, today=date.today())


@subcontractors_bp.route('/<int:sub_id>/share-document', methods=['POST'])
@login_required
def share_document(sub_id):
    """Η εταιρεία κοινοποιεί έγγραφο έργου στον υπεργολάβο."""
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('subcontractors.detail', id=sub_id))
    try:
        upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'shared_docs', str(sub_id))
        os.makedirs(upload_dir, exist_ok=True)
        file_path = None
        file_name = None
        f = request.files.get('doc_file')
        if f and f.filename:
            fname = secure_filename(f'{datetime.now().strftime("%Y%m%d%H%M%S")}_{f.filename}')
            f.save(os.path.join(upload_dir, fname))
            file_path = f'shared_docs/{sub_id}/{fname}'
            file_name = f.filename

        doc = ProjectSharedDocument(
            project_id=int(request.form['project_id']),
            subcontractor_id=sub_id,
            title=request.form['title'].strip(),
            description=request.form.get('description', '').strip(),
            doc_category=request.form.get('doc_category', 'other'),
            file_path=file_path,
            file_name=file_name,
            shared_by_id=current_user.id,
        )
        db.session.add(doc)
        db.session.commit()
        flash(f'Έγγραφο "{doc.title}" κοινοποιήθηκε.', 'success')
    except Exception as e:
        flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('subcontractors.detail', id=sub_id))


# ══════════════════════════════════════════════════════════════════════════════
# PORTAL — ΕΠΙΜΕΤΡΗΣΕΙΣ (υποβολή από υπεργολάβο)
# ══════════════════════════════════════════════════════════════════════════════

@subcontractors_bp.route('/portal/measurements')
def portal_measurements():
    sub_id = session.get('sub_portal_id')
    if not sub_id:
        return redirect(url_for('subcontractors.portal_login'))
    sub = Subcontractor.query.get_or_404(sub_id)
    contracts = sub.contracts.filter(
        SubcontractorContract.status.in_(['signed', 'active'])
    ).all()
    meas = SubcontractorMeasurement.query.join(SubcontractorContract).filter(
        SubcontractorContract.subcontractor_id == sub_id
    ).order_by(SubcontractorMeasurement.created_at.desc()).all()
    return render_template('subcontractors/portal/measurements.html',
                           sub=sub, contracts=contracts, measurements=meas, today=date.today())


@subcontractors_bp.route('/portal/measurements/submit', methods=['POST'])
def portal_submit_measurement():
    sub_id = session.get('sub_portal_id')
    if not sub_id:
        return redirect(url_for('subcontractors.portal_login'))
    try:
        qty   = float(request.form.get('quantity', 0) or 0)
        price = float(request.form.get('unit_price', 0) or 0)
        m = SubcontractorMeasurement(
            contract_id=int(request.form['contract_id']),
            title=request.form['title'].strip(),
            description=request.form.get('description', '').strip(),
            quantity=qty,
            unit=request.form.get('unit', 'τ.μ.').strip(),
            unit_price=price,
            total_amount=round(qty * price, 2),
            notes=request.form.get('notes', '').strip(),
            status='pending',
        )
        md = request.form.get('measurement_date')
        if md: m.measurement_date = datetime.strptime(md, '%Y-%m-%d').date()

        # Upload measurement file
        f = request.files.get('meas_file')
        if f and f.filename:
            upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'sub_measurements')
            os.makedirs(upload_dir, exist_ok=True)
            fname = secure_filename(f'{datetime.now().strftime("%Y%m%d%H%M%S")}_{f.filename}')
            f.save(os.path.join(upload_dir, fname))
            m.file_path = f'sub_measurements/{fname}'

        db.session.add(m)
        db.session.commit()
        flash('Επιμέτρηση υποβλήθηκε για έγκριση.', 'success')
    except Exception as e:
        flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('subcontractors.portal_measurements'))
