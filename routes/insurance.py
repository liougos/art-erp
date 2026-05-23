import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, send_from_directory
from flask_login import login_required, current_user
from datetime import datetime, date
from werkzeug.utils import secure_filename
from models import db, InsurancePolicy, Vehicle, Notification, User

insurance_bp = Blueprint('insurance', __name__)

POLICY_TYPES = [
    ('civil_liability', 'Αστική Ευθύνη Εργοταξίου'),
    ('vehicle',         'Ασφάλεια Οχήματος'),
    ('equipment',       'Ασφάλεια Εξοπλισμού'),
    ('health',          'Υγεία Εργαζομένων'),
    ('fire',            'Πυρός / Κλοπής'),
    ('accident',        'Ατυχημάτων Προσωπικού'),
    ('professional',    'Επαγγελματική Ευθύνη'),
    ('other',           'Άλλο'),
]


@insurance_bp.route('/')
@login_required
def index():
    policies = InsurancePolicy.query.order_by(InsurancePolicy.expiry_date).all()
    today = date.today()
    expiring_soon = [p for p in policies if p.days_to_expiry is not None and 0 <= p.days_to_expiry <= 30]
    expired = [p for p in policies if p.days_to_expiry is not None and p.days_to_expiry < 0]
    vehicles = Vehicle.query.order_by(Vehicle.plate).all()
    return render_template('insurance/index.html', policies=policies, today=today,
                           expiring_soon=expiring_soon, expired=expired,
                           vehicles=vehicles, policy_types=POLICY_TYPES)


@insurance_bp.route('/new', methods=['POST'])
@login_required
def new():
    try:
        pol = InsurancePolicy(
            title=request.form['title'].strip(),
            policy_type=request.form.get('policy_type', 'other'),
            insurance_company=request.form.get('insurance_company', '').strip(),
            policy_number=request.form.get('policy_number', '').strip(),
            insured_object=request.form.get('insured_object', '').strip(),
            coverage_amount=float(request.form.get('coverage_amount', 0) or 0) or None,
            annual_premium=float(request.form.get('annual_premium', 0) or 0) or None,
            payment_frequency=request.form.get('payment_frequency', 'annual'),
            auto_renew=request.form.get('auto_renew') == '1',
            vehicle_id=request.form.get('vehicle_id') or None,
            notes=request.form.get('notes', '').strip(),
            status='active',
        )
        sd = request.form.get('start_date')
        if sd: pol.start_date = datetime.strptime(sd, '%Y-%m-%d').date()
        ed = request.form.get('expiry_date')
        if ed: pol.expiry_date = datetime.strptime(ed, '%Y-%m-%d').date()

        # File upload
        f = request.files.get('policy_file')
        if f and f.filename:
            fname = secure_filename(f'insurance_{datetime.now().strftime("%Y%m%d_%H%M%S")}_{f.filename}')
            upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'insurance')
            os.makedirs(upload_dir, exist_ok=True)
            f.save(os.path.join(upload_dir, fname))
            pol.file_path = f'insurance/{fname}'
            pol.file_name = f.filename

        db.session.add(pol)
        db.session.commit()
        flash(f'Ασφαλιστήριο "{pol.title}" προστέθηκε.', 'success')
    except Exception as e:
        flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('insurance.index'))


@insurance_bp.route('/<int:id>/edit', methods=['POST'])
@login_required
def edit(id):
    pol = InsurancePolicy.query.get_or_404(id)
    pol.title = request.form['title'].strip()
    pol.policy_type = request.form.get('policy_type', pol.policy_type)
    pol.insurance_company = request.form.get('insurance_company', '').strip()
    pol.policy_number = request.form.get('policy_number', '').strip()
    pol.insured_object = request.form.get('insured_object', '').strip()
    pol.coverage_amount = float(request.form.get('coverage_amount', 0) or 0) or None
    pol.annual_premium = float(request.form.get('annual_premium', 0) or 0) or None
    pol.status = request.form.get('status', pol.status)
    pol.auto_renew = request.form.get('auto_renew') == '1'
    pol.notes = request.form.get('notes', '').strip()
    sd = request.form.get('start_date')
    if sd: pol.start_date = datetime.strptime(sd, '%Y-%m-%d').date()
    ed = request.form.get('expiry_date')
    if ed: pol.expiry_date = datetime.strptime(ed, '%Y-%m-%d').date()
    db.session.commit()
    flash('Ασφαλιστήριο ενημερώθηκε.', 'success')
    return redirect(url_for('insurance.index'))


@insurance_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('insurance.index'))
    pol = InsurancePolicy.query.get_or_404(id)
    db.session.delete(pol)
    db.session.commit()
    flash('Ασφαλιστήριο διαγράφηκε.', 'success')
    return redirect(url_for('insurance.index'))


@insurance_bp.route('/<int:id>/file')
@login_required
def view_file(id):
    pol = InsurancePolicy.query.get_or_404(id)
    if not pol.file_path:
        flash('Δεν υπάρχει αρχείο.', 'warning')
        return redirect(url_for('insurance.index'))
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], pol.file_path)
