from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import date
from models import db, SuppliesMonthlySummary

supplies_bp = Blueprint('supplies', __name__)


@supplies_bp.route('/')
@login_required
def index():
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε πρόσβαση.', 'danger')
        return redirect(url_for('dashboard.index'))

    year = int(request.args.get('year', date.today().year))

    records = {r.month: r for r in
               SuppliesMonthlySummary.query.filter_by(year=year).order_by(SuppliesMonthlySummary.month).all()}

    years = [r[0] for r in
             db.session.query(SuppliesMonthlySummary.year).distinct()
             .order_by(SuppliesMonthlySummary.year.desc()).all()]
    if year not in years:
        years = [year] + years

    # Ετήσια σύνοψη
    totals = {
        'revenue_net':   sum(float(r.revenue_net or 0)   for r in records.values()),
        'revenue_vat':   sum(float(r.revenue_vat or 0)   for r in records.values()),
        'purchases_net': sum(float(r.purchases_net or 0) for r in records.values()),
        'purchases_vat': sum(float(r.purchases_vat or 0) for r in records.values()),
        'returns_net':   sum(float(r.returns_net or 0)   for r in records.values()),
        'gross_profit':  sum(r.gross_profit               for r in records.values()),
        'net_vat':       sum(r.net_vat                    for r in records.values()),
    }

    return render_template('supplies/index.html',
                           records=records, year=year, years=years,
                           totals=totals, today=date.today())


@supplies_bp.route('/save', methods=['POST'])
@login_required
def save():
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε πρόσβαση.', 'danger')
        return redirect(url_for('supplies.index'))

    month = int(request.form['month'])
    year  = int(request.form['year'])

    record = SuppliesMonthlySummary.query.filter_by(month=month, year=year).first()
    if not record:
        record = SuppliesMonthlySummary(month=month, year=year, entered_by_id=current_user.id)
        db.session.add(record)

    record.revenue_net   = float(request.form.get('revenue_net',   0) or 0)
    record.revenue_vat   = float(request.form.get('revenue_vat',   0) or 0)
    record.purchases_net = float(request.form.get('purchases_net', 0) or 0)
    record.purchases_vat = float(request.form.get('purchases_vat', 0) or 0)
    record.returns_net   = float(request.form.get('returns_net',   0) or 0)
    record.notes         = request.form.get('notes', '').strip()
    record.entered_by_id = current_user.id

    db.session.commit()
    flash(f'Στοιχεία {record.month_label} {year} αποθηκεύτηκαν.', 'success')
    return redirect(url_for('supplies.index', year=year))


@supplies_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    if current_user.role != 'admin':
        flash('Δεν έχετε πρόσβαση.', 'danger')
        return redirect(url_for('supplies.index'))
    record = SuppliesMonthlySummary.query.get_or_404(id)
    year = record.year
    db.session.delete(record)
    db.session.commit()
    flash('Εγγραφή διαγράφηκε.', 'success')
    return redirect(url_for('supplies.index', year=year))
