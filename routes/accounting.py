from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import datetime, date
from models import db, AccountingEntry, Invoice, Project, Equipment, Vehicle, Employee

accounting_bp = Blueprint('accounting', __name__)

INCOME_CATEGORIES = ['Εισπράξεις Έργων', 'Προκαταβολές', 'Επιστροφές ΦΠΑ', 'Άλλα Έσοδα']
EXPENSE_CATEGORIES = ['Υλικά Συντήρησης', 'Μισθοδοσία', 'Ενοίκια', 'Ασφαλιστικές Εισφορές',
                      'ΔΕΗ / ΟΤΕ / Ύδρευση', 'Καύσιμα', 'Εξοπλισμός', 'Υπεργολαβίες',
                      'Λογιστικές Αμοιβές', 'Νομικές Αμοιβές', 'Marketing', 'Άλλα Έξοδα']
TAX_CATEGORIES = ['ΦΠΑ Αποδοτέος', 'Φόρος Εισοδήματος', 'Προκαταβολή Φόρου', 'Τέλη / Χαρτόσημα']


@accounting_bp.route('/')
@login_required
def index():
    year = int(request.args.get('year', date.today().year))
    month = request.args.get('month', '')
    entry_type = request.args.get('type', '')
    project_id = request.args.get('project_id', '')

    query = AccountingEntry.query.filter(AccountingEntry.period_year == year)
    if month: query = query.filter(AccountingEntry.period_month == int(month))
    if entry_type: query = query.filter_by(entry_type=entry_type)
    if project_id: query = query.filter_by(project_id=int(project_id))

    entries = query.order_by(AccountingEntry.entry_date.desc()).all()
    projects = Project.query.order_by(Project.code).all()

    total_income = sum(float(e.total_amount or 0) for e in entries if e.entry_type == 'income')
    total_expense = sum(float(e.total_amount or 0) for e in entries if e.entry_type == 'expense')
    total_tax = sum(float(e.total_amount or 0) for e in entries if e.entry_type == 'tax')
    total_payroll = sum(float(e.total_amount or 0) for e in entries if e.entry_type == 'payroll')
    net = total_income - total_expense - total_tax - total_payroll

    # Monthly summary for chart
    monthly = []
    for m in range(1, 13):
        inc = db.session.query(func.sum(AccountingEntry.total_amount)).filter(
            AccountingEntry.period_year == year,
            AccountingEntry.period_month == m,
            AccountingEntry.entry_type == 'income'
        ).scalar() or 0
        exp = db.session.query(func.sum(AccountingEntry.total_amount)).filter(
            AccountingEntry.period_year == year,
            AccountingEntry.period_month == m,
            AccountingEntry.entry_type.in_(['expense', 'payroll', 'tax'])
        ).scalar() or 0
        monthly.append({'month': m, 'income': float(inc), 'expense': float(exp)})

    # Expenses by category
    cat_data = db.session.query(
        AccountingEntry.category, func.sum(AccountingEntry.total_amount)
    ).filter(
        AccountingEntry.period_year == year,
        AccountingEntry.entry_type == 'expense'
    ).group_by(AccountingEntry.category).all()

    return render_template('accounting/index.html',
        entries=entries, projects=projects,
        total_income=total_income, total_expense=total_expense,
        total_tax=total_tax, total_payroll=total_payroll, net=net,
        monthly=monthly, cat_data=cat_data,
        income_categories=INCOME_CATEGORIES,
        expense_categories=EXPENSE_CATEGORIES,
        tax_categories=TAX_CATEGORIES,
        year=year, month=month, entry_type=entry_type, project_id=project_id,
        years=range(date.today().year, 2023, -1),
    )


@accounting_bp.route('/add', methods=['POST'])
@login_required
def add():
    net = float(request.form.get('amount_net', 0) or 0)
    vat = float(request.form.get('vat_amount', 0) or 0)
    entry_date = datetime.strptime(request.form['entry_date'], '%Y-%m-%d').date()

    entry = AccountingEntry(
        entry_date=entry_date,
        entry_type=request.form.get('entry_type', 'expense'),
        category=request.form.get('category', '').strip(),
        subcategory=request.form.get('subcategory', '').strip(),
        description=request.form.get('description', '').strip(),
        amount_net=net,
        vat_amount=vat,
        total_amount=net + vat,
        project_id=request.form.get('project_id') or None,
        status=request.form.get('status', 'pending'),
        reference=request.form.get('reference', '').strip(),
        period_month=entry_date.month,
        period_year=entry_date.year,
        notes=request.form.get('notes', '').strip(),
        created_by_id=current_user.id,
    )
    db.session.add(entry)
    db.session.commit()
    flash('Εγγραφή αποθηκεύτηκε.', 'success')
    return redirect(url_for('accounting.index'))


@accounting_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    e = AccountingEntry.query.get_or_404(id)
    db.session.delete(e)
    db.session.commit()
    flash('Εγγραφή διαγράφηκε.', 'success')
    return redirect(url_for('accounting.index'))


@accounting_bp.route('/forecast')
@login_required
def forecast():
    """Φορολογικές προβλέψεις βάσει ελληνικής φορολογίας."""
    year = int(request.args.get('year', date.today().year))

    # ── Βασικά οικονομικά στοιχεία ────────────────────────────────────────
    total_income = float(db.session.query(func.sum(AccountingEntry.total_amount)).filter(
        AccountingEntry.period_year == year,
        AccountingEntry.entry_type == 'income'
    ).scalar() or 0)

    total_expense = float(db.session.query(func.sum(AccountingEntry.total_amount)).filter(
        AccountingEntry.period_year == year,
        AccountingEntry.entry_type == 'expense'
    ).scalar() or 0)

    total_payroll = float(db.session.query(func.sum(AccountingEntry.total_amount)).filter(
        AccountingEntry.period_year == year,
        AccountingEntry.entry_type == 'payroll'
    ).scalar() or 0)

    # ΦΠΑ collected from income invoices
    vat_collected = float(db.session.query(func.sum(AccountingEntry.vat_amount)).filter(
        AccountingEntry.period_year == year,
        AccountingEntry.entry_type == 'income'
    ).scalar() or 0)

    # ΦΠΑ paid on expenses
    vat_paid = float(db.session.query(func.sum(AccountingEntry.vat_amount)).filter(
        AccountingEntry.period_year == year,
        AccountingEntry.entry_type == 'expense'
    ).scalar() or 0)

    # ── Υπολογισμός ΦΠΑ ────────────────────────────────────────────────────
    vat_payable = max(0, vat_collected - vat_paid)
    vat_credit = max(0, vat_paid - vat_collected)  # επιστροφή ΦΠΑ

    # ── Αποσβέσεις (εκτιμητικές) ──────────────────────────────────────────
    # Equipment: 10% / year (ΚΑ 1553 - μηχανήματα)
    # Vehicles: 20% / year (ΚΑ 1559 - οχήματα)
    equip_value = float(db.session.query(func.sum(Equipment.purchase_price)).scalar() or 0)
    vehicle_value = float(db.session.query(func.sum(Vehicle.purchase_price)).scalar() or 0)
    depreciation_equipment = equip_value * 0.10
    depreciation_vehicles = vehicle_value * 0.20
    total_depreciation = depreciation_equipment + depreciation_vehicles

    # ── Μισθοδοσία & ΕΦΚΑ ─────────────────────────────────────────────────
    active_employees = Employee.query.filter_by(status='active').all()
    gross_payroll = sum(float(e.basic_salary or 0) * 12 for e in active_employees)

    # ΕΦΚΑ εργοδότη (25.06% on gross, 2024 rates)
    efka_employer = gross_payroll * 0.2506
    # ΕΦΚΑ εργαζόμενου (13.87%)
    efka_employee = gross_payroll * 0.1387
    net_payroll = gross_payroll - efka_employee
    total_labor_cost = gross_payroll + efka_employer

    # ── Φόρος εισοδήματος (ΑΕ: 22%) ──────────────────────────────────────
    gross_profit = total_income - total_expense - total_payroll - total_depreciation
    taxable_income = max(0, gross_profit)
    income_tax = taxable_income * 0.22  # Ν.Π. 22%

    # Προκαταβολή φόρου επόμενου έτους (80% του φόρου)
    tax_prepayment = income_tax * 0.80

    # ── Τέλος Επιτηδεύματος ────────────────────────────────────────────────
    business_tax = 1000.0  # ΑΕ σε μη τουριστική περιοχή

    # ── Μηνιαία κατανομή ΦΠΑ ─────────────────────────────────────────────
    monthly_vat = []
    for m in range(1, 13):
        inc_vat = float(db.session.query(func.sum(AccountingEntry.vat_amount)).filter(
            AccountingEntry.period_year == year,
            AccountingEntry.period_month == m,
            AccountingEntry.entry_type == 'income'
        ).scalar() or 0)
        exp_vat = float(db.session.query(func.sum(AccountingEntry.vat_amount)).filter(
            AccountingEntry.period_year == year,
            AccountingEntry.period_month == m,
            AccountingEntry.entry_type == 'expense'
        ).scalar() or 0)
        monthly_vat.append({
            'month': m, 'collected': inc_vat, 'paid': exp_vat,
            'net': inc_vat - exp_vat
        })

    return render_template('accounting/forecast.html',
        year=year,
        years=range(date.today().year, 2023, -1),
        total_income=total_income,
        total_expense=total_expense,
        total_payroll=total_payroll,
        gross_profit=gross_profit,
        taxable_income=taxable_income,
        # ΦΠΑ
        vat_collected=vat_collected,
        vat_paid=vat_paid,
        vat_payable=vat_payable,
        vat_credit=vat_credit,
        # Αποσβέσεις
        depreciation_equipment=depreciation_equipment,
        depreciation_vehicles=depreciation_vehicles,
        total_depreciation=total_depreciation,
        # Μισθοδοσία
        gross_payroll=gross_payroll,
        efka_employer=efka_employer,
        efka_employee=efka_employee,
        net_payroll=net_payroll,
        total_labor_cost=total_labor_cost,
        active_employees=len(active_employees),
        # Φόροι
        income_tax=income_tax,
        tax_prepayment=tax_prepayment,
        business_tax=business_tax,
        total_tax_burden=income_tax + tax_prepayment + business_tax + vat_payable,
        monthly_vat=monthly_vat,
    )
