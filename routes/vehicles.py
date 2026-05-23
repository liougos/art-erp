from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from datetime import datetime, date
from models import db, Vehicle, MaintenanceRecord, Employee

vehicles_bp = Blueprint('vehicles', __name__)


@vehicles_bp.route('/')
@login_required
def index():
    vehicles = Vehicle.query.order_by(Vehicle.brand, Vehicle.model).all()
    employees = Employee.query.filter_by(status='active').order_by(Employee.last_name).all()
    today = date.today()
    thirty = today.replace(day=today.day)

    alerts = []
    for v in vehicles:
        if v.kteo_days_remaining is not None and v.kteo_days_remaining <= 30:
            alerts.append({'vehicle': v, 'type': 'ΚΤΕΟ', 'days': v.kteo_days_remaining, 'date': v.kteo_date})
        if v.insurance_days_remaining is not None and v.insurance_days_remaining <= 30:
            alerts.append({'vehicle': v, 'type': 'Ασφάλεια', 'days': v.insurance_days_remaining, 'date': v.insurance_expiry})

    return render_template('vehicles/index.html', vehicles=vehicles, employees=employees, alerts=alerts)


@vehicles_bp.route('/new', methods=['POST'])
@login_required
def new():
    v = Vehicle(
        plate=request.form['plate'].strip().upper(),
        brand=request.form.get('brand', '').strip(),
        model=request.form.get('model', '').strip(),
        year=request.form.get('year') or None,
        vehicle_type=request.form.get('vehicle_type', '').strip(),
        fuel_type=request.form.get('fuel_type', 'diesel'),
        status=request.form.get('status', 'available'),
        driver_id=request.form.get('driver_id') or None,
        insurance_company=request.form.get('insurance_company', '').strip(),
        insurance_policy=request.form.get('insurance_policy', '').strip(),
        insurance_cost=request.form.get('insurance_cost') or None,
        purchase_price=request.form.get('purchase_price') or None,
        current_km=request.form.get('current_km') or None,
        next_service_km=request.form.get('next_service_km') or None,
        notes=request.form.get('notes', '').strip(),
    )
    kteo = request.form.get('kteo_date')
    if kteo: v.kteo_date = datetime.strptime(kteo, '%Y-%m-%d').date()
    ins = request.form.get('insurance_expiry')
    if ins: v.insurance_expiry = datetime.strptime(ins, '%Y-%m-%d').date()
    pd = request.form.get('purchase_date')
    if pd: v.purchase_date = datetime.strptime(pd, '%Y-%m-%d').date()

    db.session.add(v)
    db.session.commit()
    flash(f'Όχημα {v.plate} καταχωρήθηκε.', 'success')
    return redirect(url_for('vehicles.index'))


@vehicles_bp.route('/<int:id>/maintenance/add', methods=['POST'])
@login_required
def add_maintenance(id):
    v = Vehicle.query.get_or_404(id)
    rec = MaintenanceRecord(
        item_type='vehicle',
        item_id=id,
        maintenance_type=request.form.get('maintenance_type', '').strip(),
        record_date=datetime.strptime(request.form['record_date'], '%Y-%m-%d').date(),
        description=request.form.get('description', '').strip(),
        cost=request.form.get('cost') or None,
        provider=request.form.get('provider', '').strip(),
        km_at_service=request.form.get('km_at_service') or None,
        notes=request.form.get('notes', '').strip(),
    )
    ndd = request.form.get('next_due_date')
    if ndd: rec.next_due_date = datetime.strptime(ndd, '%Y-%m-%d').date()
    ndk = request.form.get('next_due_km')
    if ndk:
        rec.next_due_km = int(ndk)
        v.next_service_km = rec.next_due_km
    v.last_service_date = rec.record_date
    if rec.km_at_service: v.last_service_km = rec.km_at_service
    db.session.add(rec)
    db.session.commit()
    flash('Service καταχωρήθηκε.', 'success')
    return redirect(url_for('vehicles.index'))


@vehicles_bp.route('/<int:id>/km', methods=['POST'])
@login_required
def update_km(id):
    v = Vehicle.query.get_or_404(id)
    v.current_km = int(request.form.get('current_km', v.current_km or 0))
    db.session.commit()
    flash('Χιλιόμετρα ενημερώθηκαν.', 'success')
    return redirect(url_for('vehicles.index'))
