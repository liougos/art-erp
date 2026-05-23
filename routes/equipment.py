from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from datetime import datetime, date
from models import db, Equipment, MaintenanceRecord, Project

equipment_bp = Blueprint('equipment', __name__)

EQUIPMENT_TYPES = [
    '3D Scanner', 'Φορητή XRF', 'Φορητός Φωτισμός UV', 'Στερεοσκόπιο',
    'Vacuum Suction Table', 'Sprayer', 'Αεροσφαιρίδιο', 'Γεννήτρια',
    'Ικρίωμα', 'Ανυψωτικό', 'Εργαλεία Χεριών', 'Χημικός Εξοπλισμός',
    'Φωτογραφικός Εξοπλισμός', 'Ηλεκτρονικός Εξοπλισμός', 'Άλλο'
]


@equipment_bp.route('/')
@login_required
def index():
    status = request.args.get('status', '')
    eq_type = request.args.get('type', '')
    q = request.args.get('q', '')

    query = Equipment.query
    if status: query = query.filter_by(status=status)
    if eq_type: query = query.filter_by(equipment_type=eq_type)
    if q: query = query.filter(Equipment.name.ilike(f'%{q}%'))

    equipments = query.order_by(Equipment.name).all()
    projects = Project.query.filter_by(status='active').all()

    today = date.today()
    maintenance_due = [e for e in equipments if e.next_maintenance and e.next_maintenance <= today]

    return render_template('equipment/index.html', equipments=equipments, projects=projects,
                           equipment_types=EQUIPMENT_TYPES, maintenance_due=maintenance_due,
                           status=status, eq_type=eq_type, q=q)


@equipment_bp.route('/new', methods=['POST'])
@login_required
def new():
    eq = Equipment(
        name=request.form['name'].strip(),
        equipment_type=request.form.get('equipment_type', '').strip(),
        brand=request.form.get('brand', '').strip(),
        model=request.form.get('model', '').strip(),
        serial_number=request.form.get('serial_number', '').strip(),
        purchase_price=request.form.get('purchase_price') or None,
        current_value=request.form.get('current_value') or None,
        status=request.form.get('status', 'available'),
        location=request.form.get('location', '').strip(),
        project_id=request.form.get('project_id') or None,
        maintenance_interval_days=request.form.get('maintenance_interval_days') or None,
        notes=request.form.get('notes', '').strip(),
    )
    pd = request.form.get('purchase_date')
    if pd: eq.purchase_date = datetime.strptime(pd, '%Y-%m-%d').date()
    nm = request.form.get('next_maintenance')
    if nm: eq.next_maintenance = datetime.strptime(nm, '%Y-%m-%d').date()
    db.session.add(eq)
    db.session.commit()
    flash(f'Εξοπλισμός "{eq.name}" καταχωρήθηκε.', 'success')
    return redirect(url_for('equipment.index'))


@equipment_bp.route('/<int:id>/maintenance/add', methods=['POST'])
@login_required
def add_maintenance(id):
    eq = Equipment.query.get_or_404(id)
    rec = MaintenanceRecord(
        item_type='equipment',
        item_id=id,
        maintenance_type=request.form.get('maintenance_type', '').strip(),
        record_date=datetime.strptime(request.form['record_date'], '%Y-%m-%d').date(),
        description=request.form.get('description', '').strip(),
        cost=request.form.get('cost') or None,
        provider=request.form.get('provider', '').strip(),
        notes=request.form.get('notes', '').strip(),
    )
    ndd = request.form.get('next_due_date')
    if ndd:
        rec.next_due_date = datetime.strptime(ndd, '%Y-%m-%d').date()
        eq.next_maintenance = rec.next_due_date
    eq.last_maintenance = rec.record_date
    db.session.add(rec)
    db.session.commit()
    flash('Εγγραφή συντήρησης αποθηκεύτηκε.', 'success')
    return redirect(url_for('equipment.index'))


@equipment_bp.route('/<int:id>/status', methods=['POST'])
@login_required
def update_status(id):
    eq = Equipment.query.get_or_404(id)
    eq.status = request.form.get('status', eq.status)
    eq.project_id = request.form.get('project_id') or None
    db.session.commit()
    flash('Κατάσταση εξοπλισμού ενημερώθηκε.', 'success')
    return redirect(url_for('equipment.index'))
