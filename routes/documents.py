import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, send_from_directory
from flask_login import login_required, current_user
from datetime import datetime, date
from werkzeug.utils import secure_filename
from models import db, Document, Project, Tender, Subcontractor

documents_bp = Blueprint('documents', __name__)

DOC_TYPES = ['Σύμβαση', 'Ιδιωτικό Συμφωνητικό', 'Άδεια', 'Πιστοποιητικό',
             'Έκθεση Κατάστασης', 'Μελέτη Συντήρησης', 'Πρωτόκολλο Παράδοσης',
             'Εγγυητική Επιστολή', 'Άλλο']


@documents_bp.route('/')
@login_required
def index():
    doc_type = request.args.get('type', '')
    status = request.args.get('status', '')
    project_id = request.args.get('project_id', '')
    q = request.args.get('q', '')

    query = Document.query
    if doc_type: query = query.filter_by(doc_type=doc_type)
    if status: query = query.filter_by(status=status)
    if project_id: query = query.filter_by(project_id=int(project_id))
    if q: query = query.filter(Document.title.ilike(f'%{q}%'))

    sub_id = request.args.get('subcontractor_id', '')
    if sub_id:
        query = query.filter_by(subcontractor_id=int(sub_id))

    docs = query.order_by(Document.created_at.desc()).all()
    projects       = Project.query.order_by(Project.code).all()
    tenders        = Tender.query.order_by(Tender.title).all()
    subcontractors = Subcontractor.query.filter_by(is_active=True).order_by(Subcontractor.company_name).all()

    today = date.today()
    expiring_soon = [d for d in docs if d.expiry_date and 0 <= (d.expiry_date - today).days <= 30]

    return render_template('documents/index.html', docs=docs, projects=projects,
                           tenders=tenders, subcontractors=subcontractors,
                           expiring_soon=expiring_soon,
                           doc_types=DOC_TYPES, doc_type=doc_type, status=status,
                           project_id=project_id, subcontractor_id=sub_id, q=q)


@documents_bp.route('/upload', methods=['POST'])
@login_required
def upload():
    file = request.files.get('doc_file')
    file_path = None
    file_name = None
    if file and file.filename:
        fname = secure_filename(f"doc_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
        upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'documents')
        os.makedirs(upload_dir, exist_ok=True)
        file.save(os.path.join(upload_dir, fname))
        file_path = f'documents/{fname}'
        file_name = file.filename

    doc = Document(
        title=request.form['title'].strip(),
        doc_type=request.form.get('doc_type', '').strip(),
        project_id=request.form.get('project_id') or None,
        tender_id=request.form.get('tender_id') or None,
        subcontractor_id=request.form.get('subcontractor_id') or None,
        version=request.form.get('version', '1.0').strip(),
        parties=request.form.get('parties', '').strip(),
        status=request.form.get('status', 'active'),
        tags=request.form.get('tags', '').strip(),
        notes=request.form.get('notes', '').strip(),
        file_path=file_path,
        file_name=file_name,
        uploaded_by_id=current_user.id,
    )
    sd = request.form.get('signing_date')
    if sd: doc.signing_date = datetime.strptime(sd, '%Y-%m-%d').date()
    ed = request.form.get('expiry_date')
    if ed: doc.expiry_date = datetime.strptime(ed, '%Y-%m-%d').date()

    db.session.add(doc)
    db.session.commit()
    flash('Το έγγραφο αποθηκεύτηκε.', 'success')
    return redirect(url_for('documents.index'))


@documents_bp.route('/download/<int:id>')
@login_required
def download(id):
    doc = Document.query.get_or_404(id)
    if doc.file_path:
        directory = os.path.join(current_app.config['UPLOAD_FOLDER'], os.path.dirname(doc.file_path))
        filename = os.path.basename(doc.file_path)
        return send_from_directory(directory, filename, as_attachment=True, download_name=doc.file_name)
    flash('Δεν υπάρχει αρχείο.', 'warning')
    return redirect(url_for('documents.index'))


@documents_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    doc = Document.query.get_or_404(id)
    db.session.delete(doc)
    db.session.commit()
    flash('Έγγραφο διαγράφηκε.', 'success')
    return redirect(url_for('documents.index'))
