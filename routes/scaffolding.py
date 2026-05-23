from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, date
from models import db, ScaffoldingItem, ScaffoldingAssignment, ScaffoldingAssignmentLine, ScaffoldingInspection, Subcontractor, Project, Employee

scaffolding_bp = Blueprint('scaffolding', __name__)

ITEM_TYPES = [
    ('frame',   'Πλαίσιο'),
    ('panel',   'Πάνελ'),
    ('tube',    'Σωλήνας'),
    ('coupler', 'Σύνδεσμος'),
    ('jack',    'Γρύλος'),
    ('plank',   'Σανίδα'),
    ('net',     'Δίχτυ Ασφαλείας'),
    ('other',   'Άλλο'),
]


@scaffolding_bp.route('/')
@login_required
def index():
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε πρόσβαση.', 'danger')
        return redirect(url_for('dashboard.index'))
    items       = ScaffoldingItem.query.order_by(ScaffoldingItem.item_type, ScaffoldingItem.code).all()
    assignments = ScaffoldingAssignment.query.filter_by(status='deployed').order_by(
        ScaffoldingAssignment.date_out.desc()).all()
    subcontractors = Subcontractor.query.filter_by(is_active=True).order_by(Subcontractor.company_name).all()
    projects       = Project.query.filter(Project.status.in_(['active','planning'])).order_by(Project.code).all()
    employees      = Employee.query.filter_by(status='active').order_by(Employee.last_name).all()
    return render_template('scaffolding/index.html',
                           items=items, assignments=assignments, item_types=ITEM_TYPES,
                           subcontractors=subcontractors, projects=projects,
                           employees=employees, today=date.today())


@scaffolding_bp.route('/item/new', methods=['POST'])
@login_required
def new_item():
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('scaffolding.index'))
    try:
        item = ScaffoldingItem(
            item_type=request.form.get('item_type', 'other'),
            code=request.form.get('code', '').strip(),
            description=request.form.get('description', '').strip(),
            quantity_owned=int(request.form.get('quantity_owned', 0) or 0),
            condition=request.form.get('condition', 'good'),
            location=request.form.get('location', '').strip(),
            notes=request.form.get('notes', '').strip(),
        )
        pp = request.form.get('purchase_price')
        pd = request.form.get('purchase_date')
        if pp: item.purchase_price = float(pp)
        if pd: item.purchase_date  = datetime.strptime(pd, '%Y-%m-%d').date()
        db.session.add(item)
        db.session.commit()
        flash(f'Εξάρτημα "{item.type_label}" προστέθηκε.', 'success')
    except Exception as e:
        flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('scaffolding.index'))


@scaffolding_bp.route('/item/<int:id>/edit', methods=['POST'])
@login_required
def edit_item(id):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('scaffolding.index'))
    item = ScaffoldingItem.query.get_or_404(id)
    item.item_type      = request.form.get('item_type', item.item_type)
    item.code           = request.form.get('code', '').strip()
    item.description    = request.form.get('description', '').strip()
    item.quantity_owned = int(request.form.get('quantity_owned', item.quantity_owned) or 0)
    item.condition      = request.form.get('condition', item.condition)
    item.location       = request.form.get('location', '').strip()
    item.notes          = request.form.get('notes', '').strip()
    db.session.commit()
    flash('Εξάρτημα ενημερώθηκε.', 'success')
    return redirect(url_for('scaffolding.index'))


@scaffolding_bp.route('/assign', methods=['POST'])
@login_required
def assign():
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('scaffolding.index'))
    try:
        asgn = ScaffoldingAssignment(
            project_id=int(request.form['project_id']),
            is_rented=request.form.get('is_rented') == '1',
            rental_supplier=request.form.get('rental_supplier', '').strip(),
            daily_rental_cost=float(request.form.get('daily_rental_cost', 0) or 0),
            assembly_by=request.form.get('assembly_by', 'internal'),
            assembly_subcontractor_id=request.form.get('assembly_subcontractor_id') or None,
            notes=request.form.get('notes', '').strip(),
        )
        do  = request.form.get('date_out')
        die = request.form.get('date_in_expected')
        if do:  asgn.date_out         = datetime.strptime(do, '%Y-%m-%d').date()
        if die: asgn.date_in_expected = datetime.strptime(die, '%Y-%m-%d').date()
        db.session.add(asgn)
        db.session.flush()
        # Lines: item_ids[] + quantities[]
        item_ids   = request.form.getlist('line_item_id[]')
        quantities = request.form.getlist('line_quantity[]')
        for iid, qty in zip(item_ids, quantities):
            if iid and qty and int(qty) > 0:
                db.session.add(ScaffoldingAssignmentLine(
                    assignment_id=asgn.id,
                    item_id=int(iid),
                    quantity=int(qty),
                ))
        db.session.commit()
        flash('Ανάθεση σκαλωσιάς δημιουργήθηκε.', 'success')
    except Exception as e:
        flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('scaffolding.index'))


@scaffolding_bp.route('/assignment/<int:id>/return', methods=['POST'])
@login_required
def return_assignment(id):
    asgn = ScaffoldingAssignment.query.get_or_404(id)
    asgn.status        = 'returned'
    asgn.date_returned = date.today()
    db.session.commit()
    flash('Σκαλωσιά επεστράφη.', 'success')
    return redirect(url_for('scaffolding.index'))


@scaffolding_bp.route('/assignment/<int:id>/inspect', methods=['POST'])
@login_required
def add_inspection(id):
    try:
        ins = ScaffoldingInspection(
            assignment_id=id,
            result=request.form.get('result', 'pass'),
            notes=request.form.get('notes', '').strip(),
            inspector_id=request.form.get('inspector_id') or None,
        )
        idate = request.form.get('inspection_date')
        ndate = request.form.get('next_inspection')
        if idate: ins.inspection_date = datetime.strptime(idate, '%Y-%m-%d').date()
        if ndate: ins.next_inspection = datetime.strptime(ndate, '%Y-%m-%d').date()
        db.session.add(ins)
        db.session.commit()
        flash('Έλεγχος ασφάλειας καταχωρήθηκε.', 'success')
    except Exception as e:
        flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('scaffolding.index'))


@scaffolding_bp.route('/history')
@login_required
def history():
    """Ιστορικό όλων των αναθέσεων."""
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε πρόσβαση.', 'danger')
        return redirect(url_for('dashboard.index'))
    project_id = request.args.get('project_id', '')
    q = ScaffoldingAssignment.query
    if project_id:
        q = q.filter_by(project_id=int(project_id))
    assignments = q.order_by(ScaffoldingAssignment.date_out.desc()).all()
    projects    = Project.query.order_by(Project.code).all()
    return render_template('scaffolding/history.html',
                           assignments=assignments, projects=projects,
                           project_id=project_id, today=date.today())
