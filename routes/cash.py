import csv
import io
import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date
from models import db, BankAccount, InvoicePayment, Invoice, BankTransaction

cash_bp = Blueprint('cash', __name__)


# ══════════════════════════════════════════════════════════════════════════════
# BANK RECONCILIATION — helper: parse uploaded file
# ══════════════════════════════════════════════════════════════════════════════

def _parse_bank_file(file_storage):
    """
    Accepts CSV or Excel uploaded by user.
    Returns list of dicts: {date, description, amount, reference}
    amount is positive for credit (income) and negative for debit (expense).
    Raises ValueError with a helpful message if it can't parse the file.
    """
    filename = file_storage.filename.lower()
    rows = []

    if filename.endswith('.xlsx') or filename.endswith('.xls'):
        import openpyxl
        wb = openpyxl.load_workbook(file_storage, data_only=True)
        ws = wb.active
        raw = [[cell.value for cell in row] for row in ws.iter_rows()]
    elif filename.endswith('.csv'):
        content = file_storage.read().decode('utf-8-sig', errors='replace')
        # Try comma, then semicolon as delimiter
        for delim in (',', ';', '\t'):
            reader = list(csv.reader(io.StringIO(content), delimiter=delim))
            if reader and len(reader[0]) >= 3:
                raw = reader
                break
        else:
            raise ValueError('Δεν μπόρεσα να διαβάσω το CSV. Χρησιμοποίησε κόμμα ή ερωτηματικό ως διαχωριστή.')
    else:
        raise ValueError('Υποστηρίζονται μόνο αρχεία .csv και .xlsx')

    if not raw or len(raw) < 2:
        raise ValueError('Το αρχείο φαίνεται άδειο.')

    # ── Column detection ──────────────────────────────────────────────────────
    # Normalise header names (lowercase, strip accents-ish)
    header_raw = [str(c or '').strip().lower() for c in raw[0]]

    def _find_col(keywords):
        for kw in keywords:
            for i, h in enumerate(header_raw):
                if kw in h:
                    return i
        return None

    date_col  = _find_col(['ημερ', 'date', 'ημ/', 'ημ.', 'dat'])
    desc_col  = _find_col(['περιγρ', 'descr', 'αιτιολ', 'details', 'detail', 'κίνηση', 'λεπτ'])
    debit_col = _find_col(['χρέωσ', 'debit', 'έξοδ', 'πληρωμ'])
    credit_col= _find_col(['πίστω', 'credit', 'είσπρ', 'εισπρ'])
    amt_col   = _find_col(['ποσό', 'amount', 'posot', 'αξία'])
    ref_col   = _find_col(['αριθμ', 'referen', 'παραστ', 'ref', 'number'])

    if date_col is None:
        raise ValueError('Δεν βρήκα στήλη ημερομηνίας. Βεβαιώσου ότι η πρώτη γραμμή είναι επικεφαλίδα.')
    if desc_col is None:
        raise ValueError('Δεν βρήκα στήλη περιγραφής/αιτιολογίας.')
    if debit_col is None and credit_col is None and amt_col is None:
        raise ValueError('Δεν βρήκα στήλη ποσού (Χρέωση/Πίστωση ή Ποσό).')

    # ── Parse rows ────────────────────────────────────────────────────────────
    def _to_float(val):
        if val is None or str(val).strip() in ('', '-', '—'):
            return 0.0
        s = str(val).replace('.', '').replace(',', '.').replace(' ', '').replace('€', '')
        try:
            return float(s)
        except ValueError:
            return 0.0

    def _to_date(val):
        if val is None:
            return None
        if isinstance(val, (datetime,)):
            return val.date()
        if hasattr(val, 'date'):  # date object
            return val
        s = str(val).strip()
        for fmt in ('%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d.%m.%Y', '%d/%m/%y'):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        return None

    for r in raw[1:]:
        if not any(c for c in r):   # skip empty rows
            continue
        d = _to_date(r[date_col] if date_col < len(r) else None)
        if d is None:
            continue
        desc = str(r[desc_col] if desc_col < len(r) else '').strip()
        if not desc:
            continue

        if debit_col is not None or credit_col is not None:
            deb = _to_float(r[debit_col] if debit_col is not None and debit_col < len(r) else 0)
            cre = _to_float(r[credit_col] if credit_col is not None and credit_col < len(r) else 0)
            amount = cre - deb   # credit positive, debit negative
        else:
            amount = _to_float(r[amt_col] if amt_col < len(r) else 0)

        ref = str(r[ref_col]).strip() if ref_col is not None and ref_col < len(r) and r[ref_col] else ''
        rows.append({'date': d, 'description': desc, 'amount': amount, 'reference': ref})

    if not rows:
        raise ValueError('Δεν βρέθηκαν έγκυρες γραμμές κινήσεων στο αρχείο.')
    return rows


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


# ══════════════════════════════════════════════════════════════════════════════
# BANK RECONCILIATION
# ══════════════════════════════════════════════════════════════════════════════

@cash_bp.route('/<int:id>/transactions')
@login_required
def transactions(id):
    """Κινήσεις & Συμφωνία λογαριασμού."""
    acc = BankAccount.query.get_or_404(id)
    status_filter = request.args.get('status', '')
    q = acc.bank_transactions.order_by(BankTransaction.transaction_date.desc())
    if status_filter:
        q = q.filter(BankTransaction.status == status_filter)
    txns = q.all()

    # Στατιστικά
    all_txns = acc.bank_transactions.all()
    stats = {
        'total':     len(all_txns),
        'unmatched': sum(1 for t in all_txns if t.status == 'unmatched'),
        'matched':   sum(1 for t in all_txns if t.status == 'matched'),
        'flagged':   sum(1 for t in all_txns if t.status == 'flagged'),
        'ignored':   sum(1 for t in all_txns if t.status == 'ignored'),
    }
    return render_template('cash/transactions.html',
                           acc=acc, txns=txns, stats=stats,
                           status_filter=status_filter, today=date.today())


@cash_bp.route('/<int:id>/transactions/import', methods=['POST'])
@login_required
def import_transactions(id):
    """Εισαγωγή κινήσεων από αρχείο CSV/Excel."""
    acc = BankAccount.query.get_or_404(id)
    f = request.files.get('bank_file')
    if not f or not f.filename:
        flash('Δεν επιλέχθηκε αρχείο.', 'danger')
        return redirect(url_for('cash.transactions', id=id))
    try:
        rows = _parse_bank_file(f)
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('cash.transactions', id=id))

    batch = f'{f.filename} — {datetime.now().strftime("%d/%m/%Y %H:%M")}'
    imported = 0
    skipped  = 0

    for row in rows:
        # Αποφυγή διπλότυπων: ίδια ημ/νία + περιγραφή + ποσό
        exists = BankTransaction.query.filter_by(
            account_id=id,
            transaction_date=row['date'],
            description=row['description'],
            amount=row['amount'],
        ).first()
        if exists:
            skipped += 1
            continue

        amt = row['amount']
        if amt > 0:
            txn_type = 'credit'
        elif 'κάρτα' in row['description'].lower() or 'card' in row['description'].lower() or 'visa' in row['description'].lower() or 'mastercard' in row['description'].lower():
            txn_type = 'card'
        elif any(kw in row['description'].lower() for kw in ['προμήθεια', 'τόκος', 'χρέωση λογαρ', 'έξοδα τήρ']):
            txn_type = 'fee'
        else:
            txn_type = 'debit'

        txn = BankTransaction(
            account_id=id,
            transaction_date=row['date'],
            description=row['description'],
            amount=amt,
            transaction_type=txn_type,
            reference=row.get('reference', ''),
            status='unmatched',
            import_batch=batch,
        )
        db.session.add(txn)
        imported += 1

    db.session.commit()
    if skipped:
        flash(f'Εισήχθησαν {imported} κινήσεις ({skipped} παραλείφθηκαν ως διπλότυπα).', 'success')
    else:
        flash(f'Εισήχθησαν {imported} κινήσεις επιτυχώς.', 'success')
    return redirect(url_for('cash.transactions', id=id))


@cash_bp.route('/transaction/<int:txn_id>/suggest')
@login_required
def suggest_invoices(txn_id):
    """AJAX: επιστρέφει τιμολόγια που πιθανώς αντιστοιχούν στην κίνηση."""
    txn = BankTransaction.query.get_or_404(txn_id)
    amt = abs(float(txn.amount))
    inv_type = 'income' if txn.is_credit else 'expense'

    # Αναζήτηση με ανοχή ±2% στο ποσό
    tolerance = amt * 0.02
    candidates = Invoice.query.filter(
        Invoice.invoice_type == inv_type,
        Invoice.total_amount.between(amt - tolerance, amt + tolerance),
    ).order_by(Invoice.invoice_date.desc()).limit(10).all()

    # Αν δεν βρούμε, επιστρέφουμε τα 10 πιο πρόσφατα του ίδιου τύπου
    if not candidates:
        candidates = Invoice.query.filter_by(
            invoice_type=inv_type
        ).order_by(Invoice.invoice_date.desc()).limit(10).all()

    results = []
    for inv in candidates:
        results.append({
            'id':      inv.id,
            'number':  inv.invoice_number or f'#{inv.id}',
            'date':    inv.invoice_date.strftime('%d/%m/%Y') if inv.invoice_date else '',
            'client':  inv.client_name or inv.supplier_name or '',
            'amount':  float(inv.total_amount or 0),
            'status':  inv.payment_status,
        })
    return jsonify(results)


@cash_bp.route('/transaction/<int:txn_id>/match', methods=['POST'])
@login_required
def match_transaction(txn_id):
    """Αντιστοίχιση κίνησης με τιμολόγιο."""
    txn = BankTransaction.query.get_or_404(txn_id)
    invoice_id = request.form.get('invoice_id')
    if not invoice_id:
        return jsonify({'ok': False, 'error': 'Δεν επιλέχθηκε τιμολόγιο.'})
    inv = Invoice.query.get(int(invoice_id))
    if not inv:
        return jsonify({'ok': False, 'error': 'Τιμολόγιο δεν βρέθηκε.'})
    txn.matched_invoice_id = inv.id
    txn.status = 'matched'
    txn.notes  = request.form.get('notes', txn.notes)
    db.session.commit()
    return jsonify({'ok': True, 'label': f'{inv.invoice_number or inv.id} — {inv.client_name or inv.supplier_name or ""}'})


@cash_bp.route('/transaction/<int:txn_id>/unmatch', methods=['POST'])
@login_required
def unmatch_transaction(txn_id):
    """Αφαίρεση αντιστοίχισης."""
    txn = BankTransaction.query.get_or_404(txn_id)
    txn.matched_invoice_id = None
    txn.status = 'unmatched'
    db.session.commit()
    return jsonify({'ok': True})


@cash_bp.route('/transaction/<int:txn_id>/flag', methods=['POST'])
@login_required
def flag_transaction(txn_id):
    """Σήμανση κίνησης για επικοινωνία με τράπεζα."""
    txn = BankTransaction.query.get_or_404(txn_id)
    txn.status      = 'flagged'
    txn.flag_reason = request.form.get('flag_reason', '').strip()
    db.session.commit()
    return jsonify({'ok': True})


@cash_bp.route('/transaction/<int:txn_id>/ignore', methods=['POST'])
@login_required
def ignore_transaction(txn_id):
    """Αγνόηση κίνησης (π.χ. πάγια χρέωση που δεν χρειάζεται τιμολόγιο)."""
    txn = BankTransaction.query.get_or_404(txn_id)
    txn.status = 'ignored'
    txn.notes  = request.form.get('notes', txn.notes or '').strip()
    db.session.commit()
    return jsonify({'ok': True})


@cash_bp.route('/transaction/<int:txn_id>/delete', methods=['POST'])
@login_required
def delete_transaction(txn_id):
    """Διαγραφή κίνησης (μόνο admin)."""
    if current_user.role != 'admin':
        return jsonify({'ok': False, 'error': 'Δεν έχετε δικαίωμα.'})
    txn = BankTransaction.query.get_or_404(txn_id)
    acc_id = txn.account_id
    db.session.delete(txn)
    db.session.commit()
    return jsonify({'ok': True})
