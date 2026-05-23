from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import date, datetime
from models import db, RecurringExpense, Project

recurring_bp = Blueprint('recurring', __name__)

CATEGORIES = [
    'Ενοίκιο', 'Δάνειο', 'Συνδρομή', 'Ασφάλεια', 'Μισθοδοσία',
    'Τηλεφωνία', 'Ίντερνετ', 'Λογισμικό', 'Leasing', 'Άλλο'
]


@recurring_bp.route('/')
@login_required
def index():
    show = request.args.get('show', 'active')
    query = RecurringExpense.query
    if show == 'active':
        query = query.filter_by(is_active=True)
    elif show == 'inactive':
        query = query.filter_by(is_active=False)
    expenses = query.order_by(RecurringExpense.next_due).all()
    today = date.today()
    overdue_count = sum(1 for e in expenses if e.is_active and e.next_due and e.next_due <= today)
    projects = Project.query.filter_by(status='active').order_by(Project.title).all()
    return render_template('recurring/index.html', expenses=expenses,
                           show=show, today=today, overdue_count=overdue_count,
                           categories=CATEGORIES, projects=projects)


@recurring_bp.route('/new', methods=['POST'])
@login_required
def new():
    try:
        start = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        exp = RecurringExpense(
            name=request.form['name'].strip(),
            amount=float(request.form['amount']),
            vat_rate=float(request.form.get('vat_rate', 24)),
            category=request.form.get('category', '').strip(),
            frequency=request.form.get('frequency', 'monthly'),
            start_date=start,
            next_due=start,
            project_id=request.form.get('project_id') or None,
            notes=request.form.get('notes', '').strip(),
            is_active=True,
        )
        db.session.add(exp)
        db.session.commit()
        flash(f'Επαναλαμβανόμενο έξοδο "{exp.name}" προστέθηκε.', 'success')
    except Exception as e:
        flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('recurring.index'))


@recurring_bp.route('/<int:id>/toggle', methods=['POST'])
@login_required
def toggle(id):
    exp = RecurringExpense.query.get_or_404(id)
    exp.is_active = not exp.is_active
    db.session.commit()
    state = 'ενεργοποιήθηκε' if exp.is_active else 'απενεργοποιήθηκε'
    flash(f'"{exp.name}" {state}.', 'info')
    return redirect(url_for('recurring.index'))


@recurring_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('recurring.index'))
    exp = RecurringExpense.query.get_or_404(id)
    name = exp.name
    db.session.delete(exp)
    db.session.commit()
    flash(f'"{name}" διαγράφηκε.', 'success')
    return redirect(url_for('recurring.index'))


@recurring_bp.route('/<int:id>/edit', methods=['POST'])
@login_required
def edit(id):
    exp = RecurringExpense.query.get_or_404(id)
    exp.name = request.form['name'].strip()
    exp.amount = float(request.form['amount'])
    exp.vat_rate = float(request.form.get('vat_rate', 24))
    exp.category = request.form.get('category', '').strip()
    exp.frequency = request.form.get('frequency', 'monthly')
    exp.notes = request.form.get('notes', '').strip()
    exp.project_id = request.form.get('project_id') or None
    nd = request.form.get('next_due')
    if nd:
        exp.next_due = datetime.strptime(nd, '%Y-%m-%d').date()
    db.session.commit()
    flash('Επαναλαμβανόμενο έξοδο ενημερώθηκε.', 'success')
    return redirect(url_for('recurring.index'))
