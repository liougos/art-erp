from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, date
from models import db, Quote, QuoteItem, Tender, Project

quotes_bp = Blueprint('quotes', __name__)


@quotes_bp.route('/')
@login_required
def index():
    status = request.args.get('status', '')
    q = Quote.query
    if status:
        q = q.filter_by(status=status)
    quotes = q.order_by(Quote.created_at.desc()).all()
    tenders = Tender.query.filter(Tender.status.in_(['new','analysis','offer_prep'])).order_by(Tender.title).all()
    return render_template('quotes/index.html', quotes=quotes, tenders=tenders, status=status, today=date.today())


@quotes_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    tenders  = Tender.query.order_by(Tender.title).all()
    projects = Project.query.filter(Project.status.in_(['active','planning'])).order_by(Project.code).all()
    if request.method == 'POST':
        quote = Quote(
            title=request.form['title'].strip(),
            client_name=request.form.get('client_name', '').strip(),
            client_email=request.form.get('client_email', '').strip(),
            client_phone=request.form.get('client_phone', '').strip(),
            client_afm=request.form.get('client_afm', '').strip(),
            tender_id=request.form.get('tender_id') or None,
            notes=request.form.get('notes', '').strip(),
            terms=request.form.get('terms', '').strip(),
            status='draft',
            created_by_id=current_user.id,
        )
        id_val = request.form.get('issue_date')
        if id_val: quote.issue_date = datetime.strptime(id_val, '%Y-%m-%d').date()
        vu = request.form.get('valid_until')
        if vu: quote.valid_until = datetime.strptime(vu, '%Y-%m-%d').date()

        db.session.add(quote)
        db.session.flush()

        # Items
        descs   = request.form.getlist('item_description[]')
        units   = request.form.getlist('item_unit[]')
        qtys    = request.form.getlist('item_quantity[]')
        prices  = request.form.getlist('item_unit_price[]')
        vats    = request.form.getlist('item_vat_rate[]')
        for i, desc in enumerate(descs):
            if not desc.strip(): continue
            item = QuoteItem(
                quote_id=quote.id,
                description=desc.strip(),
                unit=units[i] if i < len(units) else 'τεμ.',
                quantity=float(qtys[i]) if i < len(qtys) and qtys[i] else 1,
                unit_price=float(prices[i]) if i < len(prices) and prices[i] else 0,
                vat_rate=float(vats[i]) if i < len(vats) and vats[i] else 24,
                sort_order=i,
            )
            db.session.add(item)

        db.session.commit()
        flash(f'Προσφορά "{quote.title}" δημιουργήθηκε.', 'success')
        return redirect(url_for('quotes.detail', id=quote.id))
    return render_template('quotes/new.html', tenders=tenders, projects=projects, today=date.today())


@quotes_bp.route('/<int:id>')
@login_required
def detail(id):
    quote = Quote.query.get_or_404(id)
    return render_template('quotes/detail.html', quote=quote, today=date.today())


@quotes_bp.route('/<int:id>/status', methods=['POST'])
@login_required
def update_status(id):
    quote = Quote.query.get_or_404(id)
    new_status = request.form.get('status')
    if new_status in ('draft', 'sent', 'accepted', 'rejected', 'expired'):
        quote.status = new_status
        db.session.commit()
        flash(f'Κατάσταση προσφοράς: {quote.status_label}', 'success')
    return redirect(url_for('quotes.detail', id=id))


@quotes_bp.route('/<int:id>/convert', methods=['POST'])
@login_required
def convert_to_project(id):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('quotes.detail', id=id))
    quote = Quote.query.get_or_404(id)
    # Generate next project code (same logic as projects.new)
    year = date.today().year
    count = Project.query.filter(Project.code.like(f'AR-{year}-%')).count()
    next_code = f'AR-{year}-{count + 1:03d}'
    proj = Project(
        code=next_code,
        title=quote.title,
        client_name=quote.client_name,
        client_email=quote.client_email,
        client_afm=quote.client_afm,
        contract_value=quote.grand_total,
        status='planning',
        manager_id=current_user.id,
        tender_id=quote.tender_id,
    )
    db.session.add(proj)
    db.session.flush()
    quote.status = 'accepted'
    quote.converted_project_id = proj.id
    db.session.commit()
    flash(f'Προσφορά μετατράπηκε σε έργο #{proj.code}.', 'success')
    return redirect(url_for('projects.detail', id=proj.id))


@quotes_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if current_user.role not in ('admin', 'manager'):
        flash('Δεν έχετε δικαίωμα.', 'danger')
        return redirect(url_for('quotes.index'))
    quote = Quote.query.get_or_404(id)
    db.session.delete(quote)
    db.session.commit()
    flash('Προσφορά διαγράφηκε.', 'success')
    return redirect(url_for('quotes.index'))
