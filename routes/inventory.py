from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date
from models import db, MaterialItem, MaterialUsage, Project

inventory_bp = Blueprint('inventory', __name__)

CATEGORIES = [
    ('chemical',    'Χημικά / Αντιδραστήρια'),
    ('tools',       'Εργαλεία'),
    ('protective',  'Προστατευτικά Υλικά'),
    ('consumable',  'Αναλώσιμα'),
    ('equipment',   'Εξοπλισμός'),
    ('other',       'Άλλο'),
]

UNITS = ['τεμ.', 'kg', 'gr', 'lt', 'ml', 'm', 'm²', 'm³', 'συσκ.', 'ζεύγος']


@inventory_bp.route('/')
@login_required
def index():
    cat  = request.args.get('cat', '')
    q    = request.args.get('q', '')
    show = request.args.get('show', 'active')

    query = MaterialItem.query
    if show == 'active':
        query = query.filter_by(is_active=True)
    if cat:
        query = query.filter_by(category=cat)
    if q:
        query = query.filter(MaterialItem.name.ilike(f'%{q}%'))

    items = query.order_by(MaterialItem.category, MaterialItem.name).all()
    projects = Project.query.filter(Project.status.in_(['active','planning'])).order_by(Project.code).all()

    needs_reorder = [i for i in items if i.needs_reorder]
    total_value   = sum(i.stock_value for i in items)

    return render_template('inventory/index.html',
                           items=items, categories=CATEGORIES, units=UNITS,
                           projects=projects, needs_reorder=needs_reorder,
                           total_value=total_value,
                           cat=cat, q=q, show=show)


@inventory_bp.route('/new', methods=['POST'])
@login_required
def new():
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('inventory.index'))
    try:
        item = MaterialItem(
            name=request.form['name'].strip(),
            sku=request.form.get('sku', '').strip(),
            category=request.form.get('category', 'other'),
            unit=request.form.get('unit', 'τεμ.'),
            current_stock=float(request.form.get('current_stock', 0) or 0),
            min_stock=float(request.form.get('min_stock', 0) or 0),
            unit_price=float(request.form.get('unit_price', 0) or 0) or None,
            supplier=request.form.get('supplier', '').strip(),
            location=request.form.get('location', '').strip(),
            notes=request.form.get('notes', '').strip(),
        )
        db.session.add(item)
        db.session.commit()
        flash(f'Υλικό "{item.name}" προστέθηκε.', 'success')
    except Exception as e:
        flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('inventory.index'))


@inventory_bp.route('/<int:id>/edit', methods=['POST'])
@login_required
def edit(id):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('inventory.index'))
    item = MaterialItem.query.get_or_404(id)
    item.name      = request.form['name'].strip()
    item.sku       = request.form.get('sku', '').strip()
    item.category  = request.form.get('category', item.category)
    item.unit      = request.form.get('unit', item.unit)
    item.min_stock = float(request.form.get('min_stock', 0) or 0)
    item.unit_price= float(request.form.get('unit_price', 0) or 0) or None
    item.supplier  = request.form.get('supplier', '').strip()
    item.location  = request.form.get('location', '').strip()
    item.notes     = request.form.get('notes', '').strip()
    db.session.commit()
    flash('Υλικό ενημερώθηκε.', 'success')
    return redirect(url_for('inventory.index'))


@inventory_bp.route('/<int:id>/restock', methods=['POST'])
@login_required
def restock(id):
    item = MaterialItem.query.get_or_404(id)
    try:
        qty = float(request.form['quantity'])
        if qty <= 0:
            raise ValueError('Πρέπει να είναι θετικός αριθμός')
        item.current_stock = float(item.current_stock or 0) + qty
        # Update price if provided
        new_price = request.form.get('unit_price', '')
        if new_price:
            item.unit_price = float(new_price)
        db.session.commit()
        flash(f'Εισήχθησαν {qty} {item.unit} "{item.name}". Νέο απόθεμα: {float(item.current_stock):.2f}', 'success')
    except Exception as e:
        flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('inventory.index'))


@inventory_bp.route('/<int:id>/use', methods=['POST'])
@login_required
def use(id):
    item = MaterialItem.query.get_or_404(id)
    try:
        qty = float(request.form['quantity'])
        if qty <= 0:
            raise ValueError('Πρέπει να είναι θετικός αριθμός')
        if qty > float(item.current_stock or 0):
            flash(f'Ανεπαρκές απόθεμα. Διαθέσιμο: {float(item.current_stock):.2f} {item.unit}', 'warning')
            return redirect(url_for('inventory.index'))

        usage = MaterialUsage(
            material_id=id,
            project_id=request.form.get('project_id') or None,
            quantity=qty,
            unit_price_snapshot=item.unit_price,
            used_by_id=current_user.id,
            notes=request.form.get('notes', '').strip(),
        )
        ud = request.form.get('used_at')
        usage.used_at = datetime.strptime(ud, '%Y-%m-%d').date() if ud else date.today()

        item.current_stock = float(item.current_stock or 0) - qty
        db.session.add(usage)
        db.session.commit()
        flash(f'Χρήση {qty} {item.unit} "{item.name}" καταχωρήθηκε.', 'success')
    except Exception as e:
        flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('inventory.index'))


@inventory_bp.route('/<int:id>/history')
@login_required
def history(id):
    item   = MaterialItem.query.get_or_404(id)
    usages = item.usages.order_by(MaterialUsage.used_at.desc()).all()
    return render_template('inventory/history.html', item=item, usages=usages)


@inventory_bp.route('/export')
@login_required
def export_excel():
    import openpyxl
    from flask import make_response
    from io import BytesIO

    items = MaterialItem.query.filter_by(is_active=True).order_by(MaterialItem.category, MaterialItem.name).all()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Αποθήκη'
    headers = ['Όνομα','Κατηγορία','SKU','Μονάδα','Απόθεμα','Ελάχ. Απόθεμα','Τιμή Μονάδας','Αξία Αποθέματος','Προμηθευτής','Τοποθεσία']
    ws.append(headers)
    for it in items:
        ws.append([it.name, it.category, it.sku or '', it.unit,
                   float(it.current_stock or 0), float(it.min_stock or 0),
                   float(it.unit_price or 0), it.stock_value,
                   it.supplier or '', it.location or ''])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = make_response(buf.read())
    resp.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    resp.headers['Content-Disposition'] = 'attachment; filename=apothiki.xlsx'
    return resp
