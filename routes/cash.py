from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date
from models import db, BankAccount, InvoicePayment, Invoice

cash_bp = Blueprint('cash', __name__)


@cash_bp.route('/')
@login_required
def index():
    accounts = BankAccount.query.filter_by(is_active=True).order_by(BankAccount.name).all()
    total_expected = sum(a.calculated_balance for a in accounts)
    total_actual   = sum(float(a.last_actual_balance) for a in accounts if a.last_actual_balance is not None)
    return render_template('cash/index.html', accounts=accounts,
                           total_expected=total_expected, total_actual=total_actual,
                           today=date.today())


@cash_bp.route('/new', methods=['POST'])
@login_required
def new():
    try:
        acc = BankAccount(
            name=request.form['name'].strip(),
            bank_name=request.form.get('bank_name', '').strip(),
            iban=request.form.get('iban', '').strip(),
            account_number=request.form.get('account_number', '').strip(),
            opening_balance=float(request.form.get('opening_balance', 0) or 0),
            notes=request.form.get('notes', '').strip(),
        )
        od = request.form.get('opening_date')
        acc.opening_date = datetime.strptime(od, '%Y-%m-%d').date() if od else date.today()
        db.session.add(acc)
        db.session.commit()
        flash(f'Λογαριασμός "{acc.name}" προστέθηκε.', 'success')
    except Exception as e:
        flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('cash.index'))


@cash_bp.route('/<int:id>/update-balance', methods=['POST'])
@login_required
def update_balance(id):
    acc = BankAccount.query.get_or_404(id)
    try:
        acc.last_actual_balance = float(request.form['actual_balance'])
        acc.last_actual_date = date.today()
        db.session.commit()
        disc = acc.discrepancy
        if disc is not None and abs(disc) > 0.01:
            flash(f'Υπόλοιπο ενημερώθηκε. Διαφορά: {"+" if disc > 0 else ""}{disc:.2f}€ — '
                  f'{"Έχετε εισπράξει κάτι που δεν έχετε καταγράψει." if disc > 0 else "Έχετε πληρώσει κάτι που δεν έχετε καταγράψει."}',
                  'warning')
        else:
            flash('Υπόλοιπο ενημερώθηκε. Δεν βρέθηκαν διαφορές ✓', 'success')
    except Exception as e:
        flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('cash.index'))


@cash_bp.route('/<int:id>/edit', methods=['POST'])
@login_required
def edit(id):
    acc = BankAccount.query.get_or_404(id)
    acc.name = request.form['name'].strip()
    acc.bank_name = request.form.get('bank_name', '').strip()
    acc.iban = request.form.get('iban', '').strip()
    acc.opening_balance = float(request.form.get('opening_balance', acc.opening_balance) or 0)
    acc.notes = request.form.get('notes', '').strip()
    db.session.commit()
    flash('Λογαριασμός ενημερώθηκε.', 'success')
    return redirect(url_for('cash.index'))


@cash_bp.route('/<int:id>/toggle', methods=['POST'])
@login_required
def toggle(id):
    acc = BankAccount.query.get_or_404(id)
    acc.is_active = not acc.is_active
    db.session.commit()
    flash(f'Λογαριασμός {"ενεργοποιήθηκε" if acc.is_active else "απενεργοποιήθηκε"}.', 'info')
    return redirect(url_for('cash.index'))
