from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, date
from models import db, SafetyEquipment, PPEAssignment, Employee

safety_bp = Blueprint('safety', __name__)

CATEGORIES = [
    ('helmet',  'Κράνος'),
    ('gloves',  'Γάντια'),
    ('harness', 'Ζώνη Ασφαλείας'),
    ('boots',   'Μπότες Ασφαλείας'),
    ('vest',    'Γιλέκο Ασφαλείας'),
    ('mask',    'Μάσκα Προστασίας Χημικών / Αναπνευστήρας'),
    ('goggles', 'Γυαλιά Προστασίας'),
    ('other',   'Άλλο'),
]


@safety_bp.route('/')
@login_required
def index():
    cat    = request.args.get('cat', '')
    q      = SafetyEquipment.query
    if cat: q = q.filter_by(category=cat)
    items  = q.order_by(SafetyEquipment.category, SafetyEquipment.name).all()
    employees = Employee.query.filter_by(status='active').order_by(Employee.last_name).all()

    expiring_soon = [i for i in items if i.days_to_expiry is not None and 0 <= i.days_to_expiry <= 30]
    expired       = [i for i in items if i.days_to_expiry is not None and i.days_to_expiry < 0]
    assigned      = [i for i in items if i.is_assigned]

    return render_template('safety/index.html',
                           items=items, categories=CATEGORIES, employees=employees,
                           expiring_soon=expiring_soon, expired=expired,
                           assigned=assigned, cat=cat, today=date.today())


@safety_bp.route('/new', methods=['POST'])
@login_required
def new():
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('safety.index'))
    try:
        item = SafetyEquipment(
            name=request.form['name'].strip(),
            category=request.form.get('category', 'other'),
            serial_number=request.form.get('serial_number', '').strip(),
            condition=request.form.get('condition', 'good'),
            notes=request.form.get('notes', '').strip(),
        )
        pd = request.form.get('purchase_date')
        if pd: item.purchase_date = datetime.strptime(pd, '%Y-%m-%d').date()
        ed = request.form.get('expiry_date')
        if ed: item.expiry_date = datetime.strptime(ed, '%Y-%m-%d').date()
        db.session.add(item)
        db.session.commit()
        flash(f'ΜΑΠ "{item.name}" προστέθηκε.', 'success')
    except Exception as e:
        flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('safety.index'))


@safety_bp.route('/<int:id>/assign', methods=['POST'])
@login_required
def assign(id):
    item = SafetyEquipment.query.get_or_404(id)
    if item.is_assigned:
        flash('Αυτό το ΜΑΠ είναι ήδη ανατεθειμένο. Επιστρέψτε το πρώτα.', 'warning')
        return redirect(url_for('safety.index'))
    try:
        assignment = PPEAssignment(
            equipment_id=id,
            employee_id=int(request.form['employee_id']),
            notes=request.form.get('notes', '').strip(),
        )
        ad = request.form.get('assigned_date')
        assignment.assigned_date = datetime.strptime(ad, '%Y-%m-%d').date() if ad else date.today()
        db.session.add(assignment)
        db.session.commit()
        flash(f'ΜΑΠ ανατέθηκε σε {assignment.employee.full_name}.', 'success')
    except Exception as e:
        flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('safety.index'))


@safety_bp.route('/<int:id>/return', methods=['POST'])
@login_required
def return_equipment(id):
    item = SafetyEquipment.query.get_or_404(id)
    assignment = item.current_assignment
    if not assignment:
        flash('Αυτό το ΜΑΠ δεν είναι ανατεθειμένο.', 'warning')
        return redirect(url_for('safety.index'))
    assignment.returned_date = date.today()
    new_condition = request.form.get('condition')
    if new_condition:
        item.condition = new_condition
    db.session.commit()
    flash(f'ΜΑΠ επεστράφη από {assignment.employee.full_name}.', 'success')
    return redirect(url_for('safety.index'))


@safety_bp.route('/<int:id>/edit', methods=['POST'])
@login_required
def edit(id):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('safety.index'))
    item = SafetyEquipment.query.get_or_404(id)
    item.name          = request.form['name'].strip()
    item.category      = request.form.get('category', item.category)
    item.serial_number = request.form.get('serial_number', '').strip()
    item.condition     = request.form.get('condition', item.condition)
    item.notes         = request.form.get('notes', '').strip()
    pd = request.form.get('purchase_date')
    if pd: item.purchase_date = datetime.strptime(pd, '%Y-%m-%d').date()
    ed = request.form.get('expiry_date')
    if ed: item.expiry_date = datetime.strptime(ed, '%Y-%m-%d').date()
    db.session.commit()
    flash('ΜΑΠ ενημερώθηκε.', 'success')
    return redirect(url_for('safety.index'))
