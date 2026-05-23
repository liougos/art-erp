from flask import Blueprint, render_template, redirect, url_for, flash, request, make_response
from flask_login import login_required, current_user
from datetime import datetime, date
from models import db, Employee, PayrollRecord, BankAccount

payroll_bp = Blueprint('payroll', __name__)

IKA_EMPLOYEE_RATE = 13.87
IKA_EMPLOYER_RATE = 24.56


def _calc_payroll(gross, emp_rate=IKA_EMPLOYEE_RATE, er_rate=IKA_EMPLOYER_RATE, tax=0, other=0):
    ika_emp = round(gross * emp_rate / 100, 2)
    ika_er  = round(gross * er_rate  / 100, 2)
    net     = round(gross - ika_emp - tax - other, 2)
    return ika_emp, ika_er, net


@payroll_bp.route('/')
@login_required
def index():
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε πρόσβαση.', 'danger')
        return redirect(url_for('dashboard.index'))

    year  = int(request.args.get('year',  date.today().year))
    month = int(request.args.get('month', date.today().month))

    records   = PayrollRecord.query.filter_by(year=year, month=month)\
                    .join(Employee).order_by(Employee.last_name).all()
    employees = Employee.query.filter_by(status='active').order_by(Employee.last_name).all()
    accounts  = BankAccount.query.filter_by(is_active=True).order_by(BankAccount.name).all()

    # employees without a record this month
    existing_ids = {r.employee_id for r in records}
    missing_emps = [e for e in employees if e.id not in existing_ids]

    total_gross      = sum(float(r.gross_salary) for r in records)
    total_net        = sum(float(r.net_salary or 0) for r in records)
    total_ika_emp    = sum(float(r.ika_employee or 0) for r in records)
    total_ika_er     = sum(float(r.ika_employer or 0) for r in records)
    total_employer   = sum(r.total_employer_cost for r in records)

    months = [('','Επιλογή μήνα')] + [(i, lbl) for i, lbl in enumerate(
        ['','Ιανουάριος','Φεβρουάριος','Μάρτιος','Απρίλιος','Μάιος','Ιούνιος',
         'Ιούλιος','Αύγουστος','Σεπτέμβριος','Οκτώβριος','Νοέμβριος','Δεκέμβριος'], 0
    ) if i > 0]

    return render_template('payroll/index.html',
                           records=records, employees=employees, accounts=accounts,
                           missing_emps=missing_emps,
                           year=year, month=month, months=months,
                           total_gross=total_gross, total_net=total_net,
                           total_ika_emp=total_ika_emp, total_ika_er=total_ika_er,
                           total_employer=total_employer,
                           ika_emp_rate=IKA_EMPLOYEE_RATE, ika_er_rate=IKA_EMPLOYER_RATE,
                           today=date.today())


@payroll_bp.route('/generate', methods=['POST'])
@login_required
def generate():
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('payroll.index'))

    year  = int(request.form['year'])
    month = int(request.form['month'])
    emp_ids = request.form.getlist('employee_ids')
    if not emp_ids:
        flash('Επιλέξτε υπαλλήλους.', 'warning')
        return redirect(url_for('payroll.index', year=year, month=month))

    created = 0
    for eid in emp_ids:
        emp = Employee.query.get(int(eid))
        if not emp or not emp.basic_salary:
            continue
        if PayrollRecord.query.filter_by(employee_id=emp.id, month=month, year=year).first():
            continue
        gross = float(emp.basic_salary)
        ika_emp, ika_er, net = _calc_payroll(gross)
        rec = PayrollRecord(
            employee_id=emp.id, month=month, year=year,
            gross_salary=gross,
            ika_employee=ika_emp, ika_employer=ika_er,
            net_salary=net,
        )
        db.session.add(rec)
        created += 1
    db.session.commit()
    flash(f'Δημιουργήθηκαν {created} εγγραφές μισθοδοσίας.', 'success')
    return redirect(url_for('payroll.index', year=year, month=month))


@payroll_bp.route('/<int:id>/edit', methods=['POST'])
@login_required
def edit(id):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('payroll.index'))
    rec = PayrollRecord.query.get_or_404(id)
    gross = float(request.form.get('gross_salary', rec.gross_salary))
    emp_rate = float(request.form.get('ika_employee_rate', IKA_EMPLOYEE_RATE))
    er_rate  = float(request.form.get('ika_employer_rate', IKA_EMPLOYER_RATE))
    tax      = float(request.form.get('tax_withheld', 0) or 0)
    other    = float(request.form.get('other_deductions', 0) or 0)
    ika_emp, ika_er, net = _calc_payroll(gross, emp_rate, er_rate, tax, other)

    rec.gross_salary      = gross
    rec.ika_employee_rate = emp_rate
    rec.ika_employer_rate = er_rate
    rec.ika_employee      = ika_emp
    rec.ika_employer      = ika_er
    rec.tax_withheld      = tax
    rec.other_deductions  = other
    rec.net_salary        = net
    rec.days_worked       = int(request.form.get('days_worked', rec.days_worked) or 25)
    rec.days_absent       = int(request.form.get('days_absent', 0) or 0)
    rec.notes             = request.form.get('notes', '').strip()
    rec.bank_account_id   = request.form.get('bank_account_id') or None
    db.session.commit()
    flash('Εγγραφή μισθοδοσίας ενημερώθηκε.', 'success')
    return redirect(url_for('payroll.index', year=rec.year, month=rec.month))


@payroll_bp.route('/<int:id>/approve', methods=['POST'])
@login_required
def approve(id):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('payroll.index'))
    rec = PayrollRecord.query.get_or_404(id)
    rec.status = 'approved'
    db.session.commit()
    flash(f'Μισθοδοσία {rec.employee.full_name} εγκρίθηκε.', 'success')
    return redirect(url_for('payroll.index', year=rec.year, month=rec.month))


@payroll_bp.route('/<int:id>/mark-paid', methods=['POST'])
@login_required
def mark_paid(id):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('payroll.index'))
    rec = PayrollRecord.query.get_or_404(id)
    rec.status    = 'paid'
    rec.paid_date = date.today()
    db.session.commit()
    flash(f'Πληρωμή μισθού {rec.employee.full_name} καταχωρήθηκε.', 'success')
    return redirect(url_for('payroll.index', year=rec.year, month=rec.month))


@payroll_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if current_user.role != 'admin':
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('payroll.index'))
    rec = PayrollRecord.query.get_or_404(id)
    year, month = rec.year, rec.month
    db.session.delete(rec)
    db.session.commit()
    flash('Εγγραφή διαγράφηκε.', 'success')
    return redirect(url_for('payroll.index', year=year, month=month))


@payroll_bp.route('/export')
@login_required
def export_excel():
    import openpyxl
    from io import BytesIO

    year  = int(request.args.get('year',  date.today().year))
    month = int(request.args.get('month', date.today().month))
    records = PayrollRecord.query.filter_by(year=year, month=month)\
                  .join(Employee).order_by(Employee.last_name).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f'Μισθοδοσία {month}-{year}'
    ws.append(['Υπάλληλος','Μεικτές','ΙΚΑ Εργαζ.','ΙΚΑ Εργοδ.','Φόρος','Άλλες κρατ.','Καθαρές','Κόστος Εργοδ.','Ημ. Εργ.','Κατάσταση'])
    for r in records:
        ws.append([r.employee.full_name, float(r.gross_salary),
                   float(r.ika_employee or 0), float(r.ika_employer or 0),
                   float(r.tax_withheld or 0), float(r.other_deductions or 0),
                   float(r.net_salary or 0), r.total_employer_cost,
                   r.days_worked, r.status])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = make_response(buf.read())
    resp.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    resp.headers['Content-Disposition'] = f'attachment; filename=mismodosia_{year}_{month:02d}.xlsx'
    return resp
