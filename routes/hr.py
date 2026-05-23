import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, send_from_directory
from flask_login import login_required, current_user
from datetime import datetime, date
from werkzeug.utils import secure_filename
from models import db, Employee, CV, Tender, EmployeeCertification

hr_bp = Blueprint('hr', __name__)

SPECIALTIES = [
    'Συντηρητής Έργων Τέχνης', 'Αρχαιολόγος', 'Χημικός', 'Αρχιτέκτονας',
    'Πολιτικός Μηχανικός', 'Εργάτης Συντήρησης', 'Ηλεκτρολόγος', 'Υδραυλικός',
    'Οδηγός', 'Διοικητικός', 'Λογιστής', 'Νομικός', 'Άλλο'
]


@hr_bp.route('/')
@login_required
def index():
    status = request.args.get('status', 'active')
    specialty = request.args.get('specialty', '')
    q = request.args.get('q', '')

    query = Employee.query
    if status: query = query.filter_by(status=status)
    if specialty: query = query.filter_by(specialty=specialty)
    if q: query = query.filter(
        (Employee.first_name + ' ' + Employee.last_name).ilike(f'%{q}%')
    )

    employees = query.order_by(Employee.last_name, Employee.first_name).all()
    return render_template('hr/index.html', employees=employees, status=status,
                           specialty=specialty, specialties=SPECIALTIES, q=q)


@hr_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    if request.method == 'POST':
        emp = Employee(
            first_name=request.form['first_name'].strip(),
            last_name=request.form['last_name'].strip(),
            afm=request.form.get('afm', '').strip() or None,
            amka=request.form.get('amka', '').strip() or None,
            specialty=request.form.get('specialty', '').strip(),
            employment_type=request.form.get('employment_type', 'full-time'),
            basic_salary=request.form.get('basic_salary') or None,
            phone=request.form.get('phone', '').strip(),
            email=request.form.get('email', '').strip(),
            address=request.form.get('address', '').strip(),
            iban=request.form.get('iban', '').strip(),
            emergency_contact_name=request.form.get('emergency_contact_name', '').strip(),
            emergency_contact_phone=request.form.get('emergency_contact_phone', '').strip(),
            skills=request.form.get('skills', '').strip(),
            certifications=request.form.get('certifications', '').strip(),
            education=request.form.get('education', '').strip(),
            status='active',
            notes=request.form.get('notes', '').strip(),
        )
        cs = request.form.get('contract_start')
        if cs: emp.contract_start = datetime.strptime(cs, '%Y-%m-%d').date()
        ce = request.form.get('contract_end')
        if ce: emp.contract_end = datetime.strptime(ce, '%Y-%m-%d').date()

        # Photo upload
        photo = request.files.get('photo')
        if photo and photo.filename:
            fname = secure_filename(f"emp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{photo.filename}")
            upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'employees')
            os.makedirs(upload_dir, exist_ok=True)
            photo.save(os.path.join(upload_dir, fname))
            emp.photo_path = f'employees/{fname}'

        db.session.add(emp)
        db.session.commit()
        flash(f'Υπάλληλος {emp.full_name} καταχωρήθηκε.', 'success')
        return redirect(url_for('hr.employee', id=emp.id))
    return render_template('hr/new.html', specialties=SPECIALTIES)


@hr_bp.route('/<int:id>')
@login_required
def employee(id):
    emp = Employee.query.get_or_404(id)
    cvs = CV.query.filter_by(employee_id=id).order_by(CV.created_at.desc()).all()
    tenders = Tender.query.filter(Tender.status.in_(['new', 'analysis', 'offer_prep'])).order_by(Tender.title).all()
    today = date.today()
    return render_template('hr/employee.html', emp=emp, cvs=cvs, tenders=tenders, today=today)


@hr_bp.route('/<int:id>/edit', methods=['POST'])
@login_required
def edit(id):
    emp = Employee.query.get_or_404(id)
    emp.first_name = request.form['first_name'].strip()
    emp.last_name = request.form['last_name'].strip()
    emp.specialty = request.form.get('specialty', '').strip()
    emp.employment_type = request.form.get('employment_type', emp.employment_type)
    emp.basic_salary = request.form.get('basic_salary') or None
    emp.phone = request.form.get('phone', '').strip()
    emp.email = request.form.get('email', '').strip()
    emp.address = request.form.get('address', '').strip()
    emp.iban = request.form.get('iban', '').strip()
    emp.status = request.form.get('status', emp.status)
    emp.skills = request.form.get('skills', '').strip()
    emp.certifications = request.form.get('certifications', '').strip()
    emp.notes = request.form.get('notes', '').strip()
    db.session.commit()
    flash('Στοιχεία υπαλλήλου ενημερώθηκαν.', 'success')
    return redirect(url_for('hr.employee', id=id))


@hr_bp.route('/<int:id>/certification/upload', methods=['POST'])
@login_required
def upload_certification(id):
    emp = Employee.query.get_or_404(id)
    file = request.files.get('cert_file')
    if not file or not file.filename:
        flash('Επιλέξτε αρχείο.', 'warning')
        return redirect(url_for('hr.employee', id=id))

    fname = secure_filename(f"cert_{emp.last_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'certifications')
    os.makedirs(upload_dir, exist_ok=True)
    local_path = os.path.join(upload_dir, fname)
    file.save(local_path)

    cert = EmployeeCertification(
        employee_id=id,
        name=request.form.get('cert_name', file.filename).strip(),
        cert_type=request.form.get('cert_type', 'other'),
        issuer=request.form.get('issuer', '').strip(),
        notes=request.form.get('notes', '').strip(),
        file_path=f'certifications/{fname}',
        file_name=file.filename,
    )
    id_val = request.form.get('issue_date')
    if id_val: cert.issue_date = datetime.strptime(id_val, '%Y-%m-%d').date()
    ed_val = request.form.get('expiry_date')
    if ed_val: cert.expiry_date = datetime.strptime(ed_val, '%Y-%m-%d').date()

    # Optional Google Drive upload
    try:
        from services.google_drive import upload_file as drive_upload
        drive_id = drive_upload(local_path, 'certifications', subfolder=emp.full_name, filename=fname)
        if drive_id:
            cert.drive_file_id = drive_id
    except Exception:
        pass

    db.session.add(cert)
    db.session.commit()
    flash(f'Πιστοποιητικό "{cert.name}" ανέβηκε.', 'success')
    return redirect(url_for('hr.employee', id=id))


@hr_bp.route('/<int:id>/certification/<int:cert_id>/delete', methods=['POST'])
@login_required
def delete_certification(id, cert_id):
    cert = EmployeeCertification.query.filter_by(id=cert_id, employee_id=id).first_or_404()
    local = os.path.join(current_app.config['UPLOAD_FOLDER'], cert.file_path)
    if os.path.exists(local):
        os.remove(local)
    db.session.delete(cert)
    db.session.commit()
    flash('Πιστοποιητικό διαγράφηκε.', 'success')
    return redirect(url_for('hr.employee', id=id))


@hr_bp.route('/<int:id>/certification/<int:cert_id>/view')
@login_required
def view_certification(id, cert_id):
    cert = EmployeeCertification.query.filter_by(id=cert_id, employee_id=id).first_or_404()
    upload_dir = current_app.config['UPLOAD_FOLDER']
    return send_from_directory(upload_dir, cert.file_path)


@hr_bp.route('/<int:id>/cv/upload', methods=['POST'])
@login_required
def upload_cv(id):
    emp = Employee.query.get_or_404(id)
    file = request.files.get('cv_file')
    if not file or not file.filename:
        flash('Επιλέξτε αρχείο.', 'warning')
        return redirect(url_for('hr.employee', id=id))

    fname = secure_filename(f"cv_{emp.last_name}_{datetime.now().strftime('%Y%m%d')}_{file.filename}")
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'cvs')
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, fname))

    cv = CV(
        employee_id=id,
        version=request.form.get('version', 'v1.0').strip(),
        file_path=f'cvs/{fname}',
        file_name=file.filename,
        tender_id=request.form.get('tender_id') or None,
        sent_to=request.form.get('sent_to', '').strip(),
        language=request.form.get('language', 'Ελληνικά'),
        notes=request.form.get('notes', '').strip(),
    )
    st = request.form.get('sent_at')
    if st: cv.sent_at = datetime.strptime(st, '%Y-%m-%d')
    db.session.add(cv)
    db.session.commit()
    flash(f'Βιογραφικό {cv.version} ανέβηκε.', 'success')
    return redirect(url_for('hr.employee', id=id))


# ── LEAVE MANAGEMENT ────────────────────────────────────────────────────────

from models import LeaveRequest, LeaveBalance

def _count_working_days(start, end):
    """Count Mon-Fri working days between start and end, inclusive."""
    from datetime import timedelta
    days = 0
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            days += 1
        cur += timedelta(days=1)
    return days


@hr_bp.route('/leave')
@login_required
def leave_index():
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε πρόσβαση.', 'danger')
        return redirect(url_for('dashboard.index'))
    status = request.args.get('status', 'pending')
    q = LeaveRequest.query
    if status != 'all':
        q = q.filter_by(status=status)
    leaves = q.order_by(LeaveRequest.created_at.desc()).all()
    employees = Employee.query.filter_by(status='active').order_by(Employee.last_name).all()
    today = date.today()
    return render_template('hr/leave.html', leaves=leaves, employees=employees,
                           status=status, today=today)


@hr_bp.route('/leave/<int:lid>/review', methods=['POST'])
@login_required
def review_leave(lid):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('hr.leave_index'))
    leave = LeaveRequest.query.get_or_404(lid)
    action = request.form.get('action', 'approved')
    leave.status = action
    leave.reviewed_by_id = current_user.id
    leave.review_notes = request.form.get('review_notes', '').strip()
    leave.reviewed_at = datetime.utcnow()

    # Update leave balance if approved annual leave
    if action == 'approved' and leave.leave_type == 'annual':
        bal = LeaveBalance.query.filter_by(
            employee_id=leave.employee_id, year=leave.start_date.year).first()
        if not bal:
            bal = LeaveBalance(
                employee_id=leave.employee_id,
                year=leave.start_date.year,
                total_days=leave.employee.annual_leave_days or 20,
                used_days=0
            )
            db.session.add(bal)
        bal.used_days = (bal.used_days or 0) + (leave.working_days or 0)

    db.session.commit()

    # Email notification
    try:
        from services.email_service import notify_leave_decision
        notify_leave_decision(leave)
    except Exception:
        pass

    flash(f'Αίτηση {"εγκρίθηκε" if action == "approved" else "απορρίφθηκε"}.', 'success')
    return redirect(url_for('hr.leave_index'))


@hr_bp.route('/<int:id>/contract/upload', methods=['POST'])
@login_required
def upload_contract(id):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('hr.employee', id=id))
    emp = Employee.query.get_or_404(id)
    file = request.files.get('contract_file')
    if not file or not file.filename:
        flash('Επιλέξτε αρχείο.', 'warning')
        return redirect(url_for('hr.employee', id=id))
    fname = secure_filename(f'contract_{emp.last_name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}_{file.filename}')
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'contracts')
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, fname))
    emp.contract_file_path = f'contracts/{fname}'
    emp.contract_file_name = file.filename
    # Update annual leave days from form
    ald = request.form.get('annual_leave_days')
    if ald:
        emp.annual_leave_days = int(ald)
    db.session.commit()
    flash('Σύμβαση εργασίας ανέβηκε.', 'success')
    return redirect(url_for('hr.employee', id=id))


@hr_bp.route('/<int:id>/contract/view')
@login_required
def view_contract(id):
    emp = Employee.query.get_or_404(id)
    # Workers can only view their own contract
    if current_user.role == 'worker':
        worker_emp = current_user.employee
        if not worker_emp or worker_emp.id != id:
            flash('Δεν έχετε πρόσβαση.', 'danger')
            return redirect(url_for('worker.dashboard'))
    if not emp.contract_file_path:
        flash('Δεν υπάρχει σύμβαση εργασίας.', 'warning')
        return redirect(url_for('hr.employee', id=id))
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], emp.contract_file_path)
