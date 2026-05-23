from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func
from datetime import date, timedelta
from models import (db, Tender, Project, Invoice, Employee, Vehicle,
                    Equipment, LegalDocument, MaintenanceRecord, Notification)

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    today = date.today()
    thirty_days = today + timedelta(days=30)

    # ── KPIs ────────────────────────────────────────────────────────────────
    active_projects = Project.query.filter_by(status='active').count()
    active_tenders = Tender.query.filter(Tender.status.in_(['new', 'analysis', 'offer_prep'])).count()
    pending_invoices = Invoice.query.filter_by(payment_status='pending').count()
    active_employees = Employee.query.filter_by(status='active').count()

    overdue_invoices = Invoice.query.filter(
        Invoice.due_date < today,
        Invoice.payment_status != 'paid'
    ).count()

    # ── Deadline alerts ──────────────────────────────────────────────────────
    urgent_tenders = Tender.query.filter(
        Tender.submission_deadline <= thirty_days,
        Tender.status.in_(['new', 'analysis', 'offer_prep'])
    ).order_by(Tender.submission_deadline).limit(5).all()

    expiring_documents = LegalDocument.query.filter(
        LegalDocument.expiry_date <= thirty_days,
        LegalDocument.expiry_date >= today,
        LegalDocument.status == 'active'
    ).order_by(LegalDocument.expiry_date).limit(5).all()

    kteo_alerts = Vehicle.query.filter(
        Vehicle.kteo_date <= thirty_days,
        Vehicle.kteo_date >= today
    ).order_by(Vehicle.kteo_date).limit(5).all()

    insurance_alerts = Vehicle.query.filter(
        Vehicle.insurance_expiry <= thirty_days,
        Vehicle.insurance_expiry >= today
    ).order_by(Vehicle.insurance_expiry).limit(5).all()

    # ── Monthly income/expense (12 months) ──────────────────────────────────
    from sqlalchemy import extract
    monthly_data = []
    for i in range(11, -1, -1):
        m = today.replace(day=1) - timedelta(days=i * 30)
        income = db.session.query(func.sum(Invoice.total_amount)).filter(
            Invoice.invoice_type == 'income',
            extract('year', Invoice.invoice_date) == m.year,
            extract('month', Invoice.invoice_date) == m.month
        ).scalar() or 0
        expense = db.session.query(func.sum(Invoice.total_amount)).filter(
            Invoice.invoice_type == 'expense',
            extract('year', Invoice.invoice_date) == m.year,
            extract('month', Invoice.invoice_date) == m.month
        ).scalar() or 0
        monthly_data.append({'month': m.strftime('%b %Y'), 'income': float(income), 'expense': float(expense)})

    # ── Projects by status ──────────────────────────────────────────────────
    project_statuses = db.session.query(Project.status, func.count(Project.id)).group_by(Project.status).all()

    # ── Recent activity ─────────────────────────────────────────────────────
    recent_projects = Project.query.order_by(Project.updated_at.desc()).limit(5).all()
    recent_invoices = Invoice.query.order_by(Invoice.created_at.desc()).limit(5).all()

    return render_template('dashboard.html',
        active_projects=active_projects,
        active_tenders=active_tenders,
        pending_invoices=pending_invoices,
        overdue_invoices=overdue_invoices,
        active_employees=active_employees,
        urgent_tenders=urgent_tenders,
        expiring_documents=expiring_documents,
        kteo_alerts=kteo_alerts,
        insurance_alerts=insurance_alerts,
        monthly_data=monthly_data,
        project_statuses=project_statuses,
        recent_projects=recent_projects,
        recent_invoices=recent_invoices,
        today=today,
    )
