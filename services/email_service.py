"""Simple SMTP email notifications. Configure via .env:
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your@email.com
MAIL_PASSWORD=app_password
MAIL_FROM=your@email.com
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app

logger = logging.getLogger(__name__)


def send_email(to: str | list, subject: str, body_html: str, body_text: str = '') -> bool:
    """Send email. Returns True on success. Silent fail if SMTP not configured."""
    cfg = current_app.config
    server = cfg.get('MAIL_SERVER', '')
    username = cfg.get('MAIL_USERNAME', '')
    password = cfg.get('MAIL_PASSWORD', '')
    mail_from = cfg.get('MAIL_FROM', username)

    if not server or not username or not password:
        logger.debug('Email not configured — skipping send')
        return False

    recipients = [to] if isinstance(to, str) else to
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = mail_from
        msg['To'] = ', '.join(recipients)
        if body_text:
            msg.attach(MIMEText(body_text, 'plain', 'utf-8'))
        msg.attach(MIMEText(body_html, 'html', 'utf-8'))

        port = int(cfg.get('MAIL_PORT', 587))
        use_tls = str(cfg.get('MAIL_USE_TLS', 'true')).lower() == 'true'

        with smtplib.SMTP(server, port, timeout=10) as smtp:
            if use_tls:
                smtp.starttls()
            smtp.login(username, password)
            smtp.sendmail(mail_from, recipients, msg.as_string())
        logger.info(f'Email sent to {recipients}: {subject}')
        return True
    except Exception as e:
        logger.warning(f'Email send failed: {e}')
        return False


def notify_leave_request(leave_request, admin_email: str):
    """Notify admin of a new leave request."""
    emp = leave_request.employee
    subject = f'Αίτηση Άδειας — {emp.full_name}'
    body = f"""
    <h3>Νέα αίτηση άδειας</h3>
    <p><strong>Υπάλληλος:</strong> {emp.full_name}</p>
    <p><strong>Τύπος:</strong> {leave_request.type_label}</p>
    <p><strong>Από:</strong> {leave_request.start_date.strftime('%d/%m/%Y')}</p>
    <p><strong>Έως:</strong> {leave_request.end_date.strftime('%d/%m/%Y')}</p>
    <p><strong>Εργάσιμες ημέρες:</strong> {leave_request.working_days}</p>
    <p><strong>Αιτιολογία:</strong> {leave_request.reason or '—'}</p>
    """
    return send_email(admin_email, subject, body)


def notify_leave_decision(leave_request):
    """Notify employee of leave approval/rejection."""
    emp = leave_request.employee
    if not emp.email:
        return False
    approved = leave_request.status == 'approved'
    subject = f'Άδεια {"Εγκρίθηκε" if approved else "Απορρίφθηκε"} — {leave_request.start_date.strftime("%d/%m/%Y")}'
    body = f"""
    <h3>{'✅ Η άδειά σας εγκρίθηκε' if approved else '❌ Η άδειά σας απορρίφθηκε'}</h3>
    <p><strong>Τύπος:</strong> {leave_request.type_label}</p>
    <p><strong>Από:</strong> {leave_request.start_date.strftime('%d/%m/%Y')}</p>
    <p><strong>Έως:</strong> {leave_request.end_date.strftime('%d/%m/%Y')}</p>
    {'<p><strong>Σημείωση:</strong> ' + leave_request.review_notes + '</p>' if leave_request.review_notes else ''}
    """
    return send_email(emp.email, subject, body)


def notify_deadline(to: str, title: str, deadline, days_left: int):
    """Generic deadline notification."""
    subject = f'⚠️ Deadline σε {days_left} ημέρες — {title}'
    body = f"""
    <h3>Προσεχής Προθεσμία</h3>
    <p><strong>{title}</strong></p>
    <p>Λήξη: {deadline.strftime('%d/%m/%Y')} ({days_left} ημέρες)</p>
    """
    return send_email(to, subject, body)
