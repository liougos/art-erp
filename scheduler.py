from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit
import logging

logger = logging.getLogger(__name__)


def scan_tenders(app):
    """Scan ΔΙΑΥΓΕΙΑ and ΕΣΗΔΗΣ for new tenders and create notifications."""
    with app.app_context():
        from models import db, Tender, Notification
        from scrapers.diavgeia import fetch_all_new_tenders as diavgeia_tenders
        from scrapers.esidis import fetch_all_new_tenders as esidis_tenders

        found = 0

        for fetch_fn, source in [(diavgeia_tenders, 'diavgeia'), (esidis_tenders, 'esidis')]:
            try:
                results = fetch_fn()
                for r in results:
                    ada = r.get('ada', '')
                    esidis_id = r.get('id', '')
                    if source == 'diavgeia':
                        if not ada: continue
                        exists = Tender.query.filter_by(ada=ada).first()
                    else:
                        if not esidis_id: continue
                        exists = Tender.query.filter_by(esidis_id=esidis_id).first()
                    if not exists:
                        t = Tender(
                            title=r.get('title', 'Αδιευκρίνιστος τίτλος')[:500],
                            authority=r.get('authority', ''),
                            ada=ada,
                            esidis_id=esidis_id if source == 'esidis' else None,
                            source=source,
                            source_url=r.get('url', ''),
                            status='new',
                        )
                        db.session.add(t)
                        found += 1
            except Exception as e:
                logger.warning(f'{source} scan error: {e}')

        if found:
            db.session.commit()
            n = Notification(
                title=f'Νέοι Διαγωνισμοί ({found})',
                message=f'Βρέθηκαν {found} νέοι διαγωνισμοί από ΔΙΑΥΓΕΙΑ / ΕΣΗΔΗΣ.',
                link='/tenders/',
                icon='bi-megaphone',
            )
            db.session.add(n)
            db.session.commit()
            logger.info(f'Tender scan: {found} new tenders added.')
        else:
            logger.info('Tender scan: no new tenders found.')


def check_expiries(app):
    """Create notifications for documents/vehicles/equipment expiring soon."""
    with app.app_context():
        from datetime import date, timedelta
        from models import db, Notification, Vehicle, LegalDocument, Equipment, EmployeeCertification

        today = date.today()
        warn_days = 30
        threshold = today + timedelta(days=warn_days)

        messages = []

        # Vehicles: ΚΤΕΟ
        for v in Vehicle.query.filter(Vehicle.kteo_date.isnot(None)).all():
            if v.kteo_date <= threshold:
                days = (v.kteo_date - today).days
                label = f'{days} ημέρες' if days > 0 else 'ΕΛΗΞΕ'
                messages.append(f'ΚΤΕΟ {v.plate}: {label}')

        # Vehicles: insurance
        for v in Vehicle.query.filter(Vehicle.insurance_expiry.isnot(None)).all():
            if v.insurance_expiry <= threshold:
                days = (v.insurance_expiry - today).days
                label = f'{days} ημέρες' if days > 0 else 'ΕΛΗΞΕ'
                messages.append(f'Ασφάλεια {v.plate}: {label}')

        # Vehicles: service due (by km)
        for v in Vehicle.query.filter(Vehicle.next_service_km.isnot(None),
                                       Vehicle.current_km.isnot(None)).all():
            remaining = v.next_service_km - v.current_km
            if remaining <= 500:
                label = f'{remaining} km' if remaining > 0 else 'ΛΗΞΕ'
                messages.append(f'Σέρβις {v.plate}: {label} απομένουν')

        # Equipment: next maintenance date
        for eq in Equipment.query.filter(Equipment.next_maintenance.isnot(None),
                                          Equipment.status != 'retired').all():
            if eq.next_maintenance <= threshold:
                days = (eq.next_maintenance - today).days
                label = f'{days} ημέρες' if days > 0 else 'ΕΛΗΞΕ'
                messages.append(f'Συντήρηση "{eq.name[:25]}": {label}')

        # Legal documents
        for d in LegalDocument.query.filter(LegalDocument.expiry_date.isnot(None),
                                             LegalDocument.status == 'active').all():
            if d.expiry_date <= threshold:
                days = (d.expiry_date - today).days
                label = f'{days} ημέρες' if days > 0 else 'ΕΛΗΞΕ'
                messages.append(f'{d.doc_type} "{d.title[:30]}": {label}')

        # Employee certifications
        for c in EmployeeCertification.query.filter(EmployeeCertification.expiry_date.isnot(None)).all():
            if c.expiry_date <= threshold:
                days = (c.expiry_date - today).days
                label = f'{days} ημέρες' if days > 0 else 'ΕΛΗΞΕ'
                messages.append(f'Πιστοποιητικό "{c.name[:25]}" ({c.employee.full_name}): {label}')

        if messages:
            n = Notification(
                title=f'Λήξεις & Συντηρήσεις ({len(messages)})',
                message=' | '.join(messages[:5]) + (f' +{len(messages)-5} ακόμη' if len(messages) > 5 else ''),
                link='/vehicles/',
                icon='bi-exclamation-triangle',
            )
            db.session.add(n)
            db.session.commit()
            logger.info(f'Expiry check: {len(messages)} items expiring soon.')


def generate_recurring_expenses(app):
    """Generate AccountingEntry records for recurring expenses due today or overdue."""
    with app.app_context():
        from datetime import date
        from models import db, RecurringExpense, AccountingEntry

        today = date.today()
        generated = 0

        for exp in RecurringExpense.query.filter_by(is_active=True).all():
            if not exp.next_due:
                continue
            while exp.next_due <= today:
                entry = AccountingEntry(
                    entry_date=exp.next_due,
                    entry_type='expense',
                    category=exp.category or 'Επαναλαμβανόμενο',
                    description=f'{exp.name} ({exp.frequency_label})',
                    amount_net=exp.amount,
                    vat_amount=float(exp.amount) * float(exp.vat_rate) / 100,
                    total_amount=float(exp.amount) * (1 + float(exp.vat_rate) / 100),
                    project_id=exp.project_id,
                    status='pending',
                    period_month=exp.next_due.month,
                    period_year=exp.next_due.year,
                    reference=f'recurring:{exp.id}',
                )
                db.session.add(entry)
                exp.last_generated = exp.next_due
                exp.advance_next_due()
                generated += 1

        if generated:
            db.session.commit()
            logger.info(f'Recurring expenses: {generated} entries generated.')


def init_scheduler(app):
    scheduler = BackgroundScheduler(timezone='Europe/Athens')

    # Scan for new tenders every 6 hours
    scheduler.add_job(
        func=lambda: scan_tenders(app),
        trigger=IntervalTrigger(hours=6),
        id='scan_tenders',
        name='Σάρωση Διαγωνισμών',
        replace_existing=True,
    )

    # Check expiries every 24 hours
    scheduler.add_job(
        func=lambda: check_expiries(app),
        trigger=IntervalTrigger(hours=24),
        id='check_expiries',
        name='Έλεγχος Λήξεων & Συντηρήσεων',
        replace_existing=True,
    )

    # Generate recurring expenses daily at startup + every 24h
    scheduler.add_job(
        func=lambda: generate_recurring_expenses(app),
        trigger=IntervalTrigger(hours=24),
        id='recurring_expenses',
        name='Επαναλαμβανόμενα Έξοδα',
        replace_existing=True,
    )

    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())
    logger.info('APScheduler started.')
    return scheduler
