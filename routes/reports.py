from flask import Blueprint, render_template, redirect, url_for, flash, request, make_response
from flask_login import login_required, current_user
from datetime import datetime, date
from models import db, Project, Invoice, MaterialUsage, PayrollRecord, Employee, ProjectTeamMember, DailyReport, SuppliesMonthlySummary, SubcontractorContract

reports_bp = Blueprint('reports', __name__)


def _project_pl(project):
    """Return a dict with P&L breakdown for a project."""
    inv_income  = [i for i in project.invoices if i.invoice_type == 'income']
    inv_expense = [i for i in project.invoices if i.invoice_type == 'expense']

    revenue       = sum(float(i.total_amount or 0) for i in inv_income)
    direct_costs  = sum(float(i.total_amount or 0) for i in inv_expense)

    # Material costs from inventory
    mat_usages   = project.material_usages.all()
    material_cost = sum(u.line_cost for u in mat_usages)

    # Labor estimate: team member daily_rate * approved daily report count
    labor_cost = 0
    for tm in project.team:
        if tm.daily_rate:
            report_count = DailyReport.query.filter_by(
                project_id=project.id, employee_id=tm.employee_id, status='approved'
            ).count()
            labor_cost += float(tm.daily_rate) * report_count

    # Subcontractor invoice costs (SubcontractorInvoice model — separate from main Invoice)
    sub_contracts = project.subcontractor_contracts.all()
    subcontractor_cost = 0.0
    sub_invoices_list = []
    for sc in sub_contracts:
        for inv in sc.invoices.all():
            subcontractor_cost += float(inv.amount_net or 0)
            sub_invoices_list.append(inv)

    contract_value = float(project.contract_value or 0)
    total_cost     = direct_costs + material_cost + labor_cost + subcontractor_cost
    gross_profit   = (revenue or contract_value) - total_cost
    margin_pct     = round(gross_profit / (revenue or contract_value) * 100, 1) if (revenue or contract_value) else 0

    return {
        'contract_value':       contract_value,
        'revenue':              revenue,
        'direct_costs':         direct_costs,
        'material_cost':        material_cost,
        'labor_cost':           labor_cost,
        'subcontractor_cost':   subcontractor_cost,
        'total_cost':           total_cost,
        'gross_profit':         gross_profit,
        'margin_pct':           margin_pct,
        'inv_income':           inv_income,
        'inv_expense':          inv_expense,
        'mat_usages':           mat_usages,
        'sub_contracts':        sub_contracts,
        'sub_invoices_list':    sub_invoices_list,
    }


@reports_bp.route('/')
@login_required
def index():
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε πρόσβαση.', 'danger')
        return redirect(url_for('dashboard.index'))
    projects = Project.query.filter(Project.status.in_(['active', 'completed'])).order_by(Project.code).all()
    return render_template('reports/index.html', projects=projects, today=date.today())


@reports_bp.route('/project/<int:id>')
@login_required
def project_pl(id):
    project = Project.query.get_or_404(id)
    pl = _project_pl(project)
    return render_template('reports/project_pl.html', project=project, pl=pl, today=date.today())


@reports_bp.route('/vat')
@login_required
def vat_summary():
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε πρόσβαση.', 'danger')
        return redirect(url_for('dashboard.index'))

    year  = int(request.args.get('year', date.today().year))
    invoices = Invoice.query.filter(
        db.extract('year', Invoice.invoice_date) == year
    ).order_by(Invoice.invoice_date).all()

    # Group by month
    monthly = {}
    for inv in invoices:
        if not inv.invoice_date: continue
        m = inv.invoice_date.month
        if m not in monthly:
            monthly[m] = {'income_net': 0, 'income_vat': 0, 'expense_net': 0, 'expense_vat': 0}
        net = float(inv.amount_net or 0)
        vat = float(inv.vat_amount or 0)
        if inv.invoice_type == 'income':
            monthly[m]['income_net'] += net
            monthly[m]['income_vat'] += vat
        else:
            monthly[m]['expense_net'] += net
            monthly[m]['expense_vat'] += vat

    for m in monthly:
        d = monthly[m]
        d['net_vat'] = round(d['income_vat'] - d['expense_vat'], 2)

    # Supplies data from Pylon (manual entry)
    supplies = {s.month: s for s in
                SuppliesMonthlySummary.query.filter_by(year=year).all()}

    # Merge: combined net VAT per month
    for m in range(1, 13):
        s = supplies.get(m)
        proj = monthly.get(m, {})
        combined_vat = round(
            proj.get('net_vat', 0) + (s.net_vat if s else 0), 2
        )
        if m in monthly:
            monthly[m]['combined_vat'] = combined_vat
        elif s:
            monthly[m] = {
                'income_net': 0, 'income_vat': 0,
                'expense_net': 0, 'expense_vat': 0,
                'net_vat': 0, 'combined_vat': combined_vat,
            }

    month_names = ['','Ιαν','Φεβ','Μαρ','Απρ','Μαι','Ιουν','Ιουλ','Αυγ','Σεπ','Οκτ','Νοε','Δεκ']

    return render_template('reports/vat.html', monthly=monthly, year=year,
                           supplies=supplies, month_names=month_names, today=date.today())


@reports_bp.route('/invoices-excel')
@login_required
def invoices_excel():
    import openpyxl
    from io import BytesIO

    year  = request.args.get('year',  '')
    month = request.args.get('month', '')

    q = Invoice.query
    if year:  q = q.filter(db.extract('year',  Invoice.invoice_date) == int(year))
    if month: q = q.filter(db.extract('month', Invoice.invoice_date) == int(month))
    invoices = q.order_by(Invoice.invoice_date).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Τιμολόγια'
    ws.append(['Αρ.','Τύπος','Εκδότης','Ημ/νία','Καθαρή','ΦΠΑ%','ΦΠΑ','Σύνολο','Κατηγορία','Έργο','Κατάσταση'])
    for inv in invoices:
        ws.append([
            inv.invoice_number or '',
            'Έσοδο' if inv.invoice_type == 'income' else 'Έξοδο',
            inv.issuer or inv.recipient or '',
            inv.invoice_date.strftime('%d/%m/%Y') if inv.invoice_date else '',
            float(inv.amount_net or 0),
            float(inv.vat_rate or 0),
            float(inv.vat_amount or 0),
            float(inv.total_amount or 0),
            inv.category or '',
            inv.project.code if inv.project else '',
            inv.payment_status or '',
        ])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = make_response(buf.read())
    resp.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    fname = f'timologia_{year or "all"}_{month or "all"}.xlsx'
    resp.headers['Content-Disposition'] = f'attachment; filename={fname}'
    return resp


@reports_bp.route('/all-projects-pl')
@login_required
def all_projects_pl():
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε πρόσβαση.', 'danger')
        return redirect(url_for('dashboard.index'))
    projects = Project.query.filter(Project.status.in_(['active','completed'])).order_by(Project.code).all()
    rows = [(p, _project_pl(p)) for p in projects]
    return render_template('reports/all_projects_pl.html', rows=rows, today=date.today())
