import os
import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, send_from_directory, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date
from werkzeug.utils import secure_filename
from models import db, LegalDocument, Project

logger = logging.getLogger(__name__)

legal_bp = Blueprint('legal', __name__)

DOC_TYPES = [
    'Ιδιωτικό Συμφωνητικό', 'Σύμβαση Εργασίας', 'Σύμβαση Υπεργολαβίας',
    'Ασφαλιστήριο Συμβόλαιο', 'Άδεια Λειτουργίας', 'Πιστοποιητικό Εγγραφής',
    'Εγγυητική Επιστολή', 'Αγωγή / Διαφορά', 'Πληρεξούσιο', 'Άλλο'
]


@legal_bp.route('/')
@login_required
def index():
    doc_type = request.args.get('type', '')
    status = request.args.get('status', '')
    q = request.args.get('q', '')

    query = LegalDocument.query
    if doc_type: query = query.filter_by(doc_type=doc_type)
    if status: query = query.filter_by(status=status)
    if q: query = query.filter(LegalDocument.title.ilike(f'%{q}%'))

    docs = query.order_by(LegalDocument.created_at.desc()).all()
    projects = Project.query.order_by(Project.code).all()
    today = date.today()

    expiring = [d for d in docs if d.expiry_date and 0 <= (d.expiry_date - today).days <= 60]
    reminders = [d for d in docs if d.reminder_date and d.reminder_date <= today and d.status == 'active']

    return render_template('legal/index.html', docs=docs, projects=projects,
                           expiring=expiring, reminders=reminders,
                           doc_types=DOC_TYPES, doc_type=doc_type, status=status, q=q)


@legal_bp.route('/new', methods=['POST'])
@login_required
def new():
    file = request.files.get('doc_file')
    file_path = None
    file_name = None
    if file and file.filename:
        fname = secure_filename(f"legal_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
        upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'legal')
        os.makedirs(upload_dir, exist_ok=True)
        file.save(os.path.join(upload_dir, fname))
        file_path = f'legal/{fname}'
        file_name = file.filename

    doc = LegalDocument(
        title=request.form['title'].strip(),
        doc_type=request.form.get('doc_type', '').strip(),
        parties=request.form.get('parties', '').strip(),
        value=request.form.get('value') or None,
        status=request.form.get('status', 'active'),
        lawyer_name=request.form.get('lawyer_name', '').strip(),
        lawyer_contact=request.form.get('lawyer_contact', '').strip(),
        project_id=request.form.get('project_id') or None,
        auto_renew=bool(request.form.get('auto_renew')),
        file_path=file_path,
        file_name=file_name,
        notes=request.form.get('notes', '').strip(),
    )
    sd = request.form.get('signing_date')
    if sd: doc.signing_date = datetime.strptime(sd, '%Y-%m-%d').date()
    ed = request.form.get('expiry_date')
    if ed: doc.expiry_date = datetime.strptime(ed, '%Y-%m-%d').date()
    rd = request.form.get('reminder_date')
    if rd: doc.reminder_date = datetime.strptime(rd, '%Y-%m-%d').date()

    db.session.add(doc)
    db.session.commit()

    # Upload to Google Drive
    if file_path:
        try:
            from services.google_drive import upload_file as drive_upload
            local_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file_path)
            doc_type_folder = doc.doc_type or 'Άλλα'
            drive_upload(local_path, 'legal', subfolder=doc_type_folder, filename=fname)
        except Exception as e:
            logger.warning(f'Drive upload skipped: {e}')

    flash('Νομικό έγγραφο καταχωρήθηκε.', 'success')
    return redirect(url_for('legal.index'))


@legal_bp.route('/download/<int:id>')
@login_required
def download(id):
    doc = LegalDocument.query.get_or_404(id)
    if doc.file_path:
        directory = os.path.join(current_app.config['UPLOAD_FOLDER'], os.path.dirname(doc.file_path))
        return send_from_directory(directory, os.path.basename(doc.file_path),
                                   as_attachment=True, download_name=doc.file_name)
    flash('Δεν υπάρχει αρχείο.', 'warning')
    return redirect(url_for('legal.index'))


@legal_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    doc = LegalDocument.query.get_or_404(id)
    db.session.delete(doc)
    db.session.commit()
    flash('Νομικό έγγραφο διαγράφηκε.', 'success')
    return redirect(url_for('legal.index'))


@legal_bp.route('/ai-chat', methods=['POST'])
@login_required
def ai_chat():
    """AI Legal Advisor powered by Claude."""
    api_key = current_app.config.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return jsonify({'error': 'Δεν έχει οριστεί ANTHROPIC_API_KEY στο .env αρχείο.'}), 503

    data = request.get_json(silent=True) or {}
    question = (data.get('message') or '').strip()
    doc_context = (data.get('doc_context') or '').strip()

    if not question:
        return jsonify({'error': 'Κενό μήνυμα.'}), 400

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        system_prompt = (
            "Είσαι ειδικός νομικός σύμβουλος για ελληνικές εταιρείες συντήρησης αρχαιοτήτων και έργων τέχνης. "
            "Απαντάς ΠΑΝΤΑ στα ελληνικά. Χρησιμοποιείς ελληνική νομική ορολογία. "
            "Είσαι σαφής, συνοπτικός και πρακτικός. "
            "Αναφέρεις πάντα ότι για οριστικές νομικές αποφάσεις απαιτείται δικηγόρος. "
            "Γνωρίζεις: δημόσιες συμβάσεις, ΕΣΗΔΗΣ, ν.4412/2016, εργατικό δίκαιο, ασφαλιστικό δίκαιο, "
            "αρχαιολογικό νόμο (ν.3028/2002), ΦΠΑ, φορολογικά, ΚΑΤ, ΙΚΑ/ΕΦΚΑ."
        )

        user_content = question
        if doc_context:
            user_content = f"Περιεχόμενο Εγγράφου:\n{doc_context[:3000]}\n\nΕρώτηση: {question}"

        response = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=1024,
            system=system_prompt,
            messages=[{'role': 'user', 'content': user_content}],
        )
        return jsonify({'answer': response.content[0].text})

    except Exception as e:
        return jsonify({'error': f'Σφάλμα AI: {str(e)}'}), 500
