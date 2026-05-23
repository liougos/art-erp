import os
import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_from_directory, current_app
from flask_login import login_required, current_user
from datetime import datetime, date
from werkzeug.utils import secure_filename
from models import db, Tender, TenderOffer, TenderOfferItem, Project, Notification, User, TenderDocument
from scrapers import diavgeia, esidis

logger = logging.getLogger(__name__)


def _extract_pdf_text(path: str) -> str:
    """Extract text from a PDF file. Returns empty string on failure."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        parts = []
        for page in reader.pages[:30]:  # limit to 30 pages
            text = page.extract_text()
            if text:
                parts.append(text)
        return '\n'.join(parts)[:50000]  # cap at 50k chars
    except Exception as e:
        logger.warning(f'PDF text extraction failed: {e}')
        return ''

tenders_bp = Blueprint('tenders', __name__)

STATUS_FLOW = ['new', 'analysis', 'offer_prep', 'submitted', 'won', 'lost', 'cancelled', 'no_bid']


@tenders_bp.route('/')
@login_required
def index():
    status = request.args.get('status', '')
    priority = request.args.get('priority', '')
    source = request.args.get('source', '')
    q = request.args.get('q', '')

    query = Tender.query
    if status: query = query.filter_by(status=status)
    if priority: query = query.filter_by(priority=priority)
    if source: query = query.filter_by(source=source)
    if q: query = query.filter(Tender.title.ilike(f'%{q}%'))

    tenders = query.order_by(Tender.submission_deadline.asc().nullslast()).all()
    counts = {s: Tender.query.filter_by(status=s).count() for s in STATUS_FLOW}
    return render_template('tenders/index.html', tenders=tenders, counts=counts,
                           status=status, priority=priority, source=source, q=q)


@tenders_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    users = User.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        t = Tender(
            title=request.form['title'].strip(),
            description=request.form.get('description', '').strip(),
            source=request.form.get('source', 'Χειροκίνητα'),
            source_url=request.form.get('source_url', '').strip(),
            ada=request.form.get('ada', '').strip(),
            cpv_code=request.form.get('cpv_code', '').strip(),
            procuring_authority=request.form.get('procuring_authority', '').strip(),
            authority_region=request.form.get('authority_region', '').strip(),
            authority_contact=request.form.get('authority_contact', '').strip(),
            budget_estimate=request.form.get('budget_estimate') or None,
            execution_months=request.form.get('execution_months') or None,
            priority=request.form.get('priority', 'medium'),
            status='new',
            assigned_to_id=request.form.get('assigned_to_id') or None,
            notes=request.form.get('notes', '').strip(),
        )
        pub = request.form.get('publication_date')
        if pub: t.publication_date = datetime.strptime(pub, '%Y-%m-%d').date()
        dl = request.form.get('submission_deadline')
        if dl: t.submission_deadline = datetime.strptime(dl, '%Y-%m-%dT%H:%M')
        db.session.add(t)
        db.session.commit()
        flash('Ο διαγωνισμός καταχωρήθηκε.', 'success')
        return redirect(url_for('tenders.detail', id=t.id))
    return render_template('tenders/new.html', users=users)


@tenders_bp.route('/<int:id>')
@login_required
def detail(id):
    t = Tender.query.get_or_404(id)
    offers = TenderOffer.query.filter_by(tender_id=id).order_by(TenderOffer.version.desc()).all()
    docs = TenderDocument.query.filter_by(tender_id=id).order_by(TenderDocument.created_at).all()
    return render_template('tenders/detail.html', tender=t, offers=offers, docs=docs)


@tenders_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    t = Tender.query.get_or_404(id)
    users = User.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        t.title = request.form['title'].strip()
        t.description = request.form.get('description', '').strip()
        t.source = request.form.get('source', t.source)
        t.source_url = request.form.get('source_url', '').strip()
        t.ada = request.form.get('ada', '').strip()
        t.cpv_code = request.form.get('cpv_code', '').strip()
        t.procuring_authority = request.form.get('procuring_authority', '').strip()
        t.authority_region = request.form.get('authority_region', '').strip()
        t.authority_contact = request.form.get('authority_contact', '').strip()
        t.budget_estimate = request.form.get('budget_estimate') or None
        t.execution_months = request.form.get('execution_months') or None
        t.priority = request.form.get('priority', 'medium')
        t.status = request.form.get('status', t.status)
        t.win_probability = request.form.get('win_probability', 50)
        t.assigned_to_id = request.form.get('assigned_to_id') or None
        t.notes = request.form.get('notes', '').strip()
        pub = request.form.get('publication_date')
        if pub: t.publication_date = datetime.strptime(pub, '%Y-%m-%d').date()
        dl = request.form.get('submission_deadline')
        if dl: t.submission_deadline = datetime.strptime(dl, '%Y-%m-%dT%H:%M')
        db.session.commit()
        flash('Ο διαγωνισμός ενημερώθηκε.', 'success')
        return redirect(url_for('tenders.detail', id=id))
    return render_template('tenders/edit.html', tender=t, users=users)


@tenders_bp.route('/<int:id>/status/<string:new_status>', methods=['POST'])
@login_required
def change_status(id, new_status):
    t = Tender.query.get_or_404(id)
    if new_status in STATUS_FLOW:
        t.status = new_status
        db.session.commit()
        flash(f'Κατάσταση → {t.status_label}', 'success')
    return redirect(url_for('tenders.detail', id=id))


# ── Offer Builder ──────────────────────────────────────────────────────────
@tenders_bp.route('/<int:id>/offer/new', methods=['GET', 'POST'])
@login_required
def new_offer(id):
    tender = Tender.query.get_or_404(id)
    last = TenderOffer.query.filter_by(tender_id=id).order_by(TenderOffer.version.desc()).first()
    next_version = (last.version + 1) if last else 1

    if request.method == 'POST':
        offer = TenderOffer(
            tender_id=id,
            version=next_version,
            labor_cost=float(request.form.get('labor_cost', 0) or 0),
            materials_cost=float(request.form.get('materials_cost', 0) or 0),
            equipment_cost=float(request.form.get('equipment_cost', 0) or 0),
            subcontractor_cost=float(request.form.get('subcontractor_cost', 0) or 0),
            overhead_pct=float(request.form.get('overhead_pct', 15) or 15),
            profit_pct=float(request.form.get('profit_pct', 10) or 10),
            vat_pct=float(request.form.get('vat_pct', 24) or 24),
            notes=request.form.get('notes', '').strip(),
            status='draft',
        )
        direct = offer.labor_cost + offer.materials_cost + offer.equipment_cost + offer.subcontractor_cost
        overhead = direct * float(offer.overhead_pct) / 100
        profit = (direct + overhead) * float(offer.profit_pct) / 100
        net = direct + overhead + profit
        vat = net * float(offer.vat_pct) / 100
        offer.total_net = round(net, 2)
        offer.total_gross = round(net + vat, 2)
        db.session.add(offer)
        tender.our_offer_amount = offer.total_gross
        db.session.commit()
        flash(f'Προσφορά v{next_version} δημιουργήθηκε — σύνολο {offer.total_gross:,.2f}€', 'success')
        return redirect(url_for('tenders.detail', id=id))
    return render_template('tenders/offer.html', tender=tender, version=next_version)


# ── Auto-search ΕΣΗΔΗΣ / ΔΙΑΥΓΕΙΑ ─────────────────────────────────────────
@tenders_bp.route('/search-external', methods=['POST'])
@login_required
def search_external():
    source = request.form.get('source', 'diavgeia')
    results = diavgeia.fetch_all_new_tenders() if source == 'diavgeia' else esidis.fetch_all_new_tenders()
    imported = 0
    for item in results:
        exists = Tender.query.filter_by(ada=item.get('ada', '')).first() if item.get('ada') else None
        if not exists:
            t = Tender(
                title=item.get('title', 'Χωρίς τίτλο')[:600],
                source=item.get('source', source.upper()),
                source_url=item.get('url', ''),
                ada=item.get('ada', ''),
                procuring_authority=item.get('authority', ''),
                status='new',
            )
            pub = item.get('publication_date')
            if pub:
                try: t.publication_date = datetime.strptime(pub[:10], '%Y-%m-%d').date()
                except: pass
            db.session.add(t)
            imported += 1
    db.session.commit()
    flash(f'Εισήχθησαν {imported} νέοι διαγωνισμοί από {source.upper()}.', 'success')
    return redirect(url_for('tenders.index'))


@tenders_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    t = Tender.query.get_or_404(id)
    db.session.delete(t)
    db.session.commit()
    flash('Ο διαγωνισμός διαγράφηκε.', 'success')
    return redirect(url_for('tenders.index'))


# ── Tender Documents ──────────────────────────────────────────────────────

DOC_TYPES = [
    ('proclamation', 'Διακήρυξη'),
    ('technical', 'Τεχνική Έκθεση / Μελέτη'),
    ('financial', 'Οικονομική Προσφορά'),
    ('study', 'Τεχνική Περιγραφή'),
    ('qualifications', 'Δικαιολογητικά Συμμετοχής'),
    ('other', 'Άλλο'),
]


@tenders_bp.route('/<int:id>/documents/upload', methods=['POST'])
@login_required
def upload_document(id):
    t = Tender.query.get_or_404(id)
    file = request.files.get('doc_file')
    if not file or not file.filename:
        flash('Επιλέξτε αρχείο.', 'warning')
        return redirect(url_for('tenders.detail', id=id))

    fname = secure_filename(f"td_{t.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'tender_docs')
    os.makedirs(upload_dir, exist_ok=True)
    local_path = os.path.join(upload_dir, fname)
    file.save(local_path)

    # Extract text for AI
    extracted = ''
    if fname.lower().endswith('.pdf'):
        extracted = _extract_pdf_text(local_path)

    doc = TenderDocument(
        tender_id=id,
        doc_type=request.form.get('doc_type', 'other'),
        title=request.form.get('doc_title', file.filename).strip(),
        file_path=f'tender_docs/{fname}',
        file_name=file.filename,
        extracted_text=extracted,
        uploaded_by_id=current_user.id,
    )
    db.session.add(doc)
    db.session.commit()

    # Optional Drive upload
    try:
        from services.google_drive import upload_file as drive_upload
        drive_id = drive_upload(local_path, 'tenders',
                                subfolder=t.title[:40], filename=fname)
        if drive_id:
            doc.drive_file_id = drive_id
            db.session.commit()
    except Exception:
        pass

    flash(f'Έγγραφο "{doc.title}" ανέβηκε.', 'success')
    return redirect(url_for('tenders.detail', id=id) + '#documents')


@tenders_bp.route('/documents/<int:doc_id>/view')
@login_required
def view_document(doc_id):
    doc = TenderDocument.query.get_or_404(doc_id)
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], doc.file_path)


@tenders_bp.route('/documents/<int:doc_id>/delete', methods=['POST'])
@login_required
def delete_document(doc_id):
    doc = TenderDocument.query.get_or_404(doc_id)
    tid = doc.tender_id
    local = os.path.join(current_app.config['UPLOAD_FOLDER'], doc.file_path)
    if os.path.exists(local):
        os.remove(local)
    db.session.delete(doc)
    db.session.commit()
    flash('Έγγραφο διαγράφηκε.', 'success')
    return redirect(url_for('tenders.detail', id=tid) + '#documents')


# ── Tender AI Chat ────────────────────────────────────────────────────────

@tenders_bp.route('/<int:id>/ai-chat', methods=['POST'])
@login_required
def ai_chat(id):
    t = Tender.query.get_or_404(id)
    api_key = current_app.config.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return jsonify({'error': 'Δεν έχει οριστεί ANTHROPIC_API_KEY.'}), 503

    data = request.get_json(silent=True) or {}
    question = (data.get('message') or '').strip()
    if not question:
        return jsonify({'error': 'Κενό μήνυμα.'}), 400

    # Build document context from extracted text
    docs = TenderDocument.query.filter_by(tender_id=id).all()
    doc_context_parts = []
    for doc in docs:
        if doc.extracted_text:
            doc_context_parts.append(
                f'=== {doc.type_label}: {doc.title} ===\n{doc.extracted_text[:8000]}'
            )
    doc_context = '\n\n'.join(doc_context_parts)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        system_prompt = (
            "Είσαι ειδικός σύμβουλος δημοσίων διαγωνισμών για ελληνικές εταιρείες συντήρησης αρχαιοτήτων. "
            "Αναλύεις έγγραφα διαγωνισμών (διακηρύξεις, τεχνικές μελέτες, προσφορές). "
            "Απαντάς ΠΑΝΤΑ στα ελληνικά, είσαι σαφής και πρακτικός. "
            "Γνωρίζεις: ν.4412/2016 (δημόσιες συμβάσεις), ΕΣΗΔΗΣ, ΚΗΜΔΗΣ, ΕΦΚΑ, ΦΠΑ, "
            "CPV κωδικούς πολιτισμού (92521xxx, 45454100), κριτήρια ανάθεσης, εγγυητικές επιστολές."
        )

        user_content = question
        if doc_context:
            user_content = (
                f"Έγγραφα Διαγωνισμού: {t.title}\n\n"
                f"{doc_context}\n\n"
                f"--- Ερώτηση: {question}"
            )

        response = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=1500,
            system=system_prompt,
            messages=[{'role': 'user', 'content': user_content}],
        )
        return jsonify({'answer': response.content[0].text})
    except Exception as e:
        return jsonify({'error': f'Σφάλμα AI: {str(e)}'}), 500
