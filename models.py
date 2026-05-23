from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta

db = SQLAlchemy()

# ── USERS ──────────────────────────────────────────────────────────────────
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    full_name = db.Column(db.String(150))
    role = db.Column(db.String(50), default='user')  # admin, manager, user, worker
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)

    employee = db.relationship('Employee', foreign_keys=[employee_id], backref=db.backref('user_account', uselist=False))

    def set_password(self, pw): self.password_hash = generate_password_hash(pw, method='pbkdf2:sha256')
    def check_password(self, pw): return check_password_hash(self.password_hash, pw)
    def __repr__(self): return f'<User {self.username}>'

# ── NOTIFICATIONS ──────────────────────────────────────────────────────────
class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    title = db.Column(db.String(300))
    message = db.Column(db.Text)
    notif_type = db.Column(db.String(50))  # tender, deadline, maintenance, payment
    reference_id = db.Column(db.Integer)
    reference_type = db.Column(db.String(50))
    link = db.Column(db.String(500))
    icon = db.Column(db.String(100), default='bi-bell')
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ── TENDERS (ΔΙΑΓΩΝΙΣΜΟΙ) ──────────────────────────────────────────────────
class Tender(db.Model):
    __tablename__ = 'tenders'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(600), nullable=False)
    description = db.Column(db.Text)
    source = db.Column(db.String(50))  # ΕΣΗΔΗΣ, ΔΙΑΥΓΕΙΑ, ΚΗΜΔΗΣ, Χειροκίνητα
    source_url = db.Column(db.String(800))
    ada = db.Column(db.String(100))        # ΑΔΑΜ / ΑΔΑ από ΔΙΑΥΓΕΙΑ
    esidis_id = db.Column(db.String(100)) # ID από ΕΣΗΔΗΣ
    cpv_code = db.Column(db.String(30))
    category = db.Column(db.String(150))
    procuring_authority = db.Column(db.String(400))
    authority_region = db.Column(db.String(150))
    authority_contact = db.Column(db.String(300))
    publication_date = db.Column(db.Date)
    submission_deadline = db.Column(db.DateTime)
    execution_months = db.Column(db.Integer)
    budget_estimate = db.Column(db.Numeric(14, 2))
    our_offer_amount = db.Column(db.Numeric(14, 2))
    status = db.Column(db.String(50), default='new')
    # new | analysis | offer_prep | submitted | won | lost | cancelled | no_bid
    priority = db.Column(db.String(20), default='medium')  # high | medium | low
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    win_probability = db.Column(db.Integer, default=50)  # %
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assigned_to = db.relationship('User', backref='assigned_tenders')
    offers = db.relationship('TenderOffer', backref='tender', lazy='dynamic', cascade='all, delete-orphan')
    projects = db.relationship('Project', backref='tender', lazy='dynamic')
    cvs = db.relationship('CV', backref='tender', lazy='dynamic')

    @property
    def days_to_deadline(self):
        if self.submission_deadline:
            delta = self.submission_deadline.date() - date.today()
            return delta.days
        return None

    @property
    def status_label(self):
        labels = {
            'new': 'Νέος', 'analysis': 'Ανάλυση', 'offer_prep': 'Προετοιμασία Προσφοράς',
            'submitted': 'Υποβλήθηκε', 'won': 'Κερδήθηκε', 'lost': 'Χάθηκε',
            'cancelled': 'Ακυρώθηκε', 'no_bid': 'Δεν Διαγωνιστήκαμε'
        }
        return labels.get(self.status, self.status)

    @property
    def status_color(self):
        colors = {
            'new': 'info', 'analysis': 'warning', 'offer_prep': 'primary',
            'submitted': 'secondary', 'won': 'success', 'lost': 'danger',
            'cancelled': 'dark', 'no_bid': 'light'
        }
        return colors.get(self.status, 'secondary')

class TenderOffer(db.Model):
    __tablename__ = 'tender_offers'
    id = db.Column(db.Integer, primary_key=True)
    tender_id = db.Column(db.Integer, db.ForeignKey('tenders.id'), nullable=False)
    version = db.Column(db.Integer, default=1)
    labor_cost = db.Column(db.Numeric(14, 2), default=0)
    materials_cost = db.Column(db.Numeric(14, 2), default=0)
    equipment_cost = db.Column(db.Numeric(14, 2), default=0)
    subcontractor_cost = db.Column(db.Numeric(14, 2), default=0)
    overhead_pct = db.Column(db.Numeric(5, 2), default=15)
    profit_pct = db.Column(db.Numeric(5, 2), default=10)
    vat_pct = db.Column(db.Numeric(5, 2), default=24)
    total_net = db.Column(db.Numeric(14, 2), default=0)
    total_gross = db.Column(db.Numeric(14, 2), default=0)
    status = db.Column(db.String(50), default='draft')  # draft | final | submitted | won | lost
    submitted_at = db.Column(db.DateTime)
    ranking = db.Column(db.Integer)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('TenderOfferItem', backref='offer', lazy='dynamic', cascade='all, delete-orphan')

class TenderOfferItem(db.Model):
    __tablename__ = 'tender_offer_items'
    id = db.Column(db.Integer, primary_key=True)
    offer_id = db.Column(db.Integer, db.ForeignKey('tender_offers.id'), nullable=False)
    description = db.Column(db.String(500))
    unit = db.Column(db.String(50))
    quantity = db.Column(db.Numeric(10, 3))
    unit_price = db.Column(db.Numeric(12, 2))
    total = db.Column(db.Numeric(14, 2))
    category = db.Column(db.String(50))  # labor, material, equipment, subcontractor

# ── PROJECTS (ΕΡΓΑ) ────────────────────────────────────────────────────────
class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True)  # e.g. AR-2026-001
    title = db.Column(db.String(600), nullable=False)
    description = db.Column(db.Text)
    tender_id = db.Column(db.Integer, db.ForeignKey('tenders.id'))
    contract_type = db.Column(db.String(50), default='public')  # public | private
    client_name = db.Column(db.String(400))
    client_afm = db.Column(db.String(20))
    client_contact = db.Column(db.String(300))
    client_email = db.Column(db.String(150))
    location = db.Column(db.String(400))
    site_address = db.Column(db.String(400))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    contract_value = db.Column(db.Numeric(14, 2))
    total_budget = db.Column(db.Numeric(14, 2))
    spent_budget = db.Column(db.Numeric(14, 2), default=0)
    status = db.Column(db.String(50), default='planning')
    # planning | active | paused | completed | cancelled
    progress_pct = db.Column(db.Integer, default=0)
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    conservation_type = db.Column(db.String(200))  # e.g. τοιχογραφίες, γλυπτά, κτήρια
    monument_category = db.Column(db.String(100))  # Α΄ κατηγορίας, Β΄ κατηγορίας, etc.
    supervising_authority = db.Column(db.String(300))  # Εφορεία Αρχαιοτήτων
    study_file_path = db.Column(db.String(600))   # admin-only technical study
    study_file_name = db.Column(db.String(400))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    manager = db.relationship('User', backref='managed_projects')
    phases = db.relationship('ProjectPhase', backref='project', lazy='dynamic', order_by='ProjectPhase.order_num')
    logs = db.relationship('ProjectLog', backref='project', lazy='dynamic')
    invoices = db.relationship('Invoice', backref='project', lazy='dynamic')
    documents = db.relationship('Document', backref='project', lazy='dynamic')
    team = db.relationship('ProjectTeamMember', backref='project', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def budget_used_pct(self):
        if self.total_budget and float(self.total_budget) > 0:
            return round(float(self.spent_budget or 0) / float(self.total_budget) * 100, 1)
        return 0

    @property
    def days_remaining(self):
        if self.end_date:
            return (self.end_date - date.today()).days
        return None

    @property
    def status_label(self):
        return {'planning': 'Σχεδιασμός', 'active': 'Σε Εξέλιξη', 'paused': 'Σε Παύση',
                'completed': 'Ολοκληρώθηκε', 'cancelled': 'Ακυρώθηκε'}.get(self.status, self.status)

class ProjectPhase(db.Model):
    __tablename__ = 'project_phases'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    name = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    order_num = db.Column(db.Integer, default=0)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    budget = db.Column(db.Numeric(14, 2))
    status = db.Column(db.String(50), default='pending')  # pending | active | completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ProjectTeamMember(db.Model):
    __tablename__ = 'project_team'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    role = db.Column(db.String(200))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    daily_rate = db.Column(db.Numeric(10, 2))

    employee = db.relationship('Employee', backref='project_assignments')

class ProjectLog(db.Model):
    __tablename__ = 'project_logs'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    log_date = db.Column(db.Date, nullable=False, default=date.today)
    description = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    weather = db.Column(db.String(80))
    workers_count = db.Column(db.Integer)
    hours_worked = db.Column(db.Numeric(5, 1))
    phase_id = db.Column(db.Integer, db.ForeignKey('project_phases.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship('User', backref='project_logs')

# ── INVOICES (ΤΙΜΟΛΟΓΙΑ) ───────────────────────────────────────────────────
class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(150))
    invoice_type = db.Column(db.String(50))  # income | expense
    issuer = db.Column(db.String(400))
    issuer_afm = db.Column(db.String(20))
    recipient = db.Column(db.String(400))
    amount_net = db.Column(db.Numeric(14, 2))
    vat_rate = db.Column(db.Numeric(5, 2), default=24)
    vat_amount = db.Column(db.Numeric(14, 2))
    total_amount = db.Column(db.Numeric(14, 2))
    invoice_date = db.Column(db.Date)
    due_date = db.Column(db.Date)
    category = db.Column(db.String(150))  # υλικά, εργασία, εξοπλισμός, υπεργολαβία, γενικά
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    payment_status = db.Column(db.String(50), default='pending')  # pending | paid | overdue | partial
    payment_date = db.Column(db.Date)
    payment_method = db.Column(db.String(80))
    image_path = db.Column(db.String(600))
    source = db.Column(db.String(50), default='manual')  # manual | photo | email
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    @property
    def total_paid(self):
        return sum(float(p.amount) for p in self.payments)

    @property
    def remaining_balance(self):
        return round(float(self.total_amount or 0) - self.total_paid, 2)

    @property
    def is_overdue(self):
        return self.due_date and self.due_date < date.today() and self.payment_status != 'paid'

# ── DOCUMENTS (ΕΓΓΡΑΦΑ) ────────────────────────────────────────────────────
class Document(db.Model):
    __tablename__ = 'documents'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(600), nullable=False)
    doc_type = db.Column(db.String(100))
    # contract | permit | certificate | report | study | protocol | insurance | other
    project_id       = db.Column(db.Integer, db.ForeignKey('projects.id'))
    tender_id        = db.Column(db.Integer, db.ForeignKey('tenders.id'))
    subcontractor_id = db.Column(db.Integer, db.ForeignKey('subcontractors.id'))
    version = db.Column(db.String(20), default='1.0')
    file_path = db.Column(db.String(600))
    file_name = db.Column(db.String(400))
    signing_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date)
    status = db.Column(db.String(50), default='active')  # draft | active | expired | archived
    parties = db.Column(db.Text)
    tags = db.Column(db.String(600))
    notes = db.Column(db.Text)
    reminder_days = db.Column(db.Integer, default=30)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    subcontractor = db.relationship('Subcontractor',
                                    foreign_keys=[subcontractor_id],
                                    backref=db.backref('linked_documents', lazy='dynamic'))
    uploaded_by   = db.relationship('User', foreign_keys=[uploaded_by_id])

    @property
    def days_to_expiry(self):
        if self.expiry_date:
            return (self.expiry_date - date.today()).days
        return None

# ── HR (ΑΝΘΡΩΠΙΝΟ ΔΥΝΑΜΙΚΟ) ───────────────────────────────────────────────
class Employee(db.Model):
    __tablename__ = 'employees'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    afm = db.Column(db.String(20), unique=True)
    amka = db.Column(db.String(20))
    specialty = db.Column(db.String(300))
    # συντηρητής, χημικός, αρχαιολόγος, εργάτης, μηχανικός, οδηγός
    employment_type = db.Column(db.String(80))  # full-time | part-time | freelance | seasonal
    contract_start = db.Column(db.Date)
    contract_end = db.Column(db.Date)
    basic_salary = db.Column(db.Numeric(10, 2))
    phone = db.Column(db.String(30))
    email = db.Column(db.String(150))
    address = db.Column(db.String(400))
    iban = db.Column(db.String(34))
    emergency_contact_name = db.Column(db.String(200))
    emergency_contact_phone = db.Column(db.String(30))
    skills = db.Column(db.Text)
    certifications = db.Column(db.Text)
    education = db.Column(db.Text)
    status = db.Column(db.String(50), default='active')  # active | on_leave | inactive | terminated
    photo_path = db.Column(db.String(600))
    annual_leave_days = db.Column(db.Integer, default=20)
    contract_file_path = db.Column(db.String(600))
    contract_file_name = db.Column(db.String(400))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    cvs = db.relationship('CV', backref='employee', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def full_name(self): return f'{self.first_name} {self.last_name}'

class CV(db.Model):
    __tablename__ = 'cvs'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    version = db.Column(db.String(30), default='v1.0')
    file_path = db.Column(db.String(600))
    file_name = db.Column(db.String(400))
    tender_id = db.Column(db.Integer, db.ForeignKey('tenders.id'))
    sent_to = db.Column(db.String(400))
    sent_at = db.Column(db.DateTime)
    language = db.Column(db.String(30), default='Ελληνικά')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ── EQUIPMENT (ΕΞΟΠΛΙΣΜΟΣ) ────────────────────────────────────────────────
class Equipment(db.Model):
    __tablename__ = 'equipment'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(400), nullable=False)
    equipment_type = db.Column(db.String(150))
    brand = db.Column(db.String(150))
    model = db.Column(db.String(150))
    serial_number = db.Column(db.String(150))
    purchase_date = db.Column(db.Date)
    purchase_price = db.Column(db.Numeric(14, 2))
    current_value = db.Column(db.Numeric(14, 2))
    status = db.Column(db.String(50), default='available')
    # available | in_use | maintenance | retired
    location = db.Column(db.String(300))
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    assigned_employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    last_maintenance = db.Column(db.Date)
    next_maintenance = db.Column(db.Date)
    maintenance_interval_days = db.Column(db.Integer)
    photo_path = db.Column(db.String(600))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assigned_employee = db.relationship('Employee', foreign_keys=[assigned_employee_id],
                                        backref=db.backref('assigned_equipment', lazy='dynamic'))
    maintenance_records = db.relationship('MaintenanceRecord',
        primaryjoin="and_(MaintenanceRecord.item_type=='equipment', foreign(MaintenanceRecord.item_id)==Equipment.id)",
        lazy='dynamic', viewonly=True)

# ── VEHICLES (ΟΧΗΜΑΤΑ) ────────────────────────────────────────────────────
class Vehicle(db.Model):
    __tablename__ = 'vehicles'
    id = db.Column(db.Integer, primary_key=True)
    plate = db.Column(db.String(30), unique=True, nullable=False)
    brand = db.Column(db.String(100))
    model = db.Column(db.String(100))
    year = db.Column(db.Integer)
    vehicle_type = db.Column(db.String(80))  # van | truck | car | pickup
    fuel_type = db.Column(db.String(50))     # diesel | petrol | electric | hybrid
    status = db.Column(db.String(50), default='available')
    driver_id = db.Column(db.Integer, db.ForeignKey('employees.id'))
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    kteo_date = db.Column(db.Date)
    insurance_expiry = db.Column(db.Date)
    insurance_company = db.Column(db.String(300))
    insurance_policy = db.Column(db.String(150))
    insurance_cost = db.Column(db.Numeric(10, 2))
    purchase_date = db.Column(db.Date)
    purchase_price = db.Column(db.Numeric(14, 2))
    current_km = db.Column(db.Integer)
    last_service_km = db.Column(db.Integer)
    next_service_km = db.Column(db.Integer)
    last_service_date = db.Column(db.Date)
    photo_path = db.Column(db.String(600))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    driver = db.relationship('Employee', backref='vehicles_driven')

    @property
    def kteo_days_remaining(self):
        if self.kteo_date: return (self.kteo_date - date.today()).days
        return None

    @property
    def insurance_days_remaining(self):
        if self.insurance_expiry: return (self.insurance_expiry - date.today()).days
        return None

class MaintenanceRecord(db.Model):
    __tablename__ = 'maintenance_records'
    id = db.Column(db.Integer, primary_key=True)
    item_type = db.Column(db.String(20))  # equipment | vehicle
    item_id = db.Column(db.Integer)
    maintenance_type = db.Column(db.String(150))
    record_date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text)
    cost = db.Column(db.Numeric(12, 2))
    provider = db.Column(db.String(300))
    next_due_date = db.Column(db.Date)
    next_due_km = db.Column(db.Integer)
    km_at_service = db.Column(db.Integer)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ── ACCOUNTING (ΛΟΓΙΣΤΗΡΙΟ) ────────────────────────────────────────────────
class AccountingEntry(db.Model):
    __tablename__ = 'accounting_entries'
    id = db.Column(db.Integer, primary_key=True)
    entry_date = db.Column(db.Date, nullable=False)
    entry_type = db.Column(db.String(50))  # income | expense | tax | payroll | transfer
    category = db.Column(db.String(150))
    subcategory = db.Column(db.String(150))
    description = db.Column(db.String(600))
    amount_net = db.Column(db.Numeric(14, 2))
    vat_amount = db.Column(db.Numeric(14, 2), default=0)
    total_amount = db.Column(db.Numeric(14, 2))
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'))
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    status = db.Column(db.String(50), default='pending')  # pending | confirmed | reconciled
    reference = db.Column(db.String(300))
    period_month = db.Column(db.Integer)
    period_year = db.Column(db.Integer)
    notes = db.Column(db.Text)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ── LEGAL (ΝΟΜΙΚΟ) ─────────────────────────────────────────────────────────
class LegalDocument(db.Model):
    __tablename__ = 'legal_documents'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(600), nullable=False)
    doc_type = db.Column(db.String(100))
    # private_contract | insurance | license | permit | dispute | certification | other
    parties = db.Column(db.Text)
    signing_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date)
    value = db.Column(db.Numeric(14, 2))
    status = db.Column(db.String(50), default='active')  # draft | active | expired | terminated | disputed
    lawyer_name = db.Column(db.String(300))
    lawyer_contact = db.Column(db.String(300))
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    file_path = db.Column(db.String(600))
    file_name = db.Column(db.String(400))
    reminder_date = db.Column(db.Date)
    auto_renew = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def days_to_expiry(self):
        if self.expiry_date: return (self.expiry_date - date.today()).days
        return None

# ── DAILY REPORTS (ΗΜΕΡΗΣΙΕΣ ΑΝΑΦΟΡΕΣ) ────────────────────────────────────
class DailyReport(db.Model):
    __tablename__ = 'daily_reports'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    submitted_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    report_date = db.Column(db.Date, nullable=False, default=date.today)
    work_done = db.Column(db.Text, nullable=False)
    hours_worked = db.Column(db.Numeric(4, 1), default=8)
    workers_present = db.Column(db.Integer, default=1)
    weather = db.Column(db.String(80))
    problems = db.Column(db.Text)
    materials_used = db.Column(db.Text)
    next_steps = db.Column(db.Text)
    progress_pct = db.Column(db.Integer)   # 0-100
    status = db.Column(db.String(30), default='pending')  # pending | approved | rejected
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    reviewer_notes = db.Column(db.Text)
    reviewed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship('Project', backref=db.backref('daily_reports', lazy='dynamic'))
    employee = db.relationship('Employee', backref=db.backref('daily_reports', lazy='dynamic'))
    author = db.relationship('User', foreign_keys=[submitted_by])
    reviewer = db.relationship('User', foreign_keys=[reviewer_id])

# ── PROJECT MESSAGES (CHAT ΑΝΑ ΕΡΓΟ) ───────────────────────────────────────
class ProjectMessage(db.Model):
    __tablename__ = 'project_messages'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship('Project', backref=db.backref('messages', lazy='dynamic', order_by='ProjectMessage.created_at'))
    user = db.relationship('User', backref='project_messages')

# ── RECURRING EXPENSES (ΕΠΑΝΑΛΑΜΒΑΝΟΜΕΝΑ ΕΞΟΔΑ) ────────────────────────────
class RecurringExpense(db.Model):
    __tablename__ = 'recurring_expenses'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(300), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    vat_rate = db.Column(db.Numeric(5, 2), default=24)
    category = db.Column(db.String(150))
    frequency = db.Column(db.String(30), default='monthly')  # weekly|monthly|quarterly|yearly
    start_date = db.Column(db.Date, nullable=False)
    next_due = db.Column(db.Date)
    last_generated = db.Column(db.Date)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship('Project', backref=db.backref('recurring_expenses', lazy='dynamic'))

    @property
    def frequency_label(self):
        return {'weekly':'Εβδομαδιαία','monthly':'Μηνιαία','quarterly':'Τριμηνιαία','yearly':'Ετήσια'}.get(self.frequency, self.frequency)

    def advance_next_due(self):
        from dateutil.relativedelta import relativedelta
        if not self.next_due: return
        d = self.next_due
        if self.frequency == 'weekly':    self.next_due = d + relativedelta(weeks=1)
        elif self.frequency == 'monthly': self.next_due = d + relativedelta(months=1)
        elif self.frequency == 'quarterly': self.next_due = d + relativedelta(months=3)
        elif self.frequency == 'yearly':  self.next_due = d + relativedelta(years=1)

# ── EMPLOYEE CERTIFICATIONS (ΠΙΣΤΟΠΟΙΗΣΕΙΣ) ────────────────────────────────
class EmployeeCertification(db.Model):
    __tablename__ = 'employee_certifications'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    name = db.Column(db.String(300), nullable=False)
    cert_type = db.Column(db.String(80))  # degree|license|cv|training|other
    issuer = db.Column(db.String(300))
    issue_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date)
    file_path = db.Column(db.String(600))
    file_name = db.Column(db.String(400))
    notes = db.Column(db.Text)
    drive_file_id = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    employee = db.relationship('Employee', backref=db.backref('certifications_files', lazy='dynamic', cascade='all, delete-orphan'))

# ── PROJECT EVENTS / CALENDAR (ΗΜΕΡΟΛΟΓΙΟ ΕΡΓΟΥ) ───────────────────────────
class ProjectEvent(db.Model):
    __tablename__ = 'project_events'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    event_type = db.Column(db.String(80), default='other')
    # scaffolding | closure | milestone | inspection | delivery | meeting | other
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)
    description = db.Column(db.Text)
    milestone_target_pct = db.Column(db.Integer)  # target completion % for milestones
    achieved = db.Column(db.Boolean, default=False)
    color = db.Column(db.String(20), default='#c9a84c')
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship('Project', backref=db.backref('events', lazy='dynamic', order_by='ProjectEvent.start_date'))
    created_by = db.relationship('User', backref='created_events')

    @property
    def type_label(self):
        return {
            'scaffolding': 'Σκαλωσιά', 'closure': 'Κλειστός χώρος',
            'milestone': 'Στόχος/Ορόσημο', 'inspection': 'Επιθεώρηση',
            'delivery': 'Παράδοση', 'meeting': 'Σύσκεψη', 'other': 'Άλλο'
        }.get(self.event_type, self.event_type)

    @property
    def type_color(self):
        return {
            'scaffolding': '#6f42c1', 'closure': '#dc3545',
            'milestone': '#c9a84c', 'inspection': '#0dcaf0',
            'delivery': '#198754', 'meeting': '#0d6efd', 'other': '#6c757d'
        }.get(self.event_type, '#6c757d')

# ── MATERIAL REQUESTS (ΑΙΤΗΣΕΙΣ ΑΝΑΛΩΣΙΜΩΝ) ────────────────────────────────
class MaterialRequest(db.Model):
    __tablename__ = 'material_requests'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    requested_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    request_type = db.Column(db.String(50), default='materials')  # materials | equipment
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    quantity = db.Column(db.String(100))
    urgency = db.Column(db.String(30), default='normal')  # low | normal | high | urgent
    status = db.Column(db.String(50), default='pending')  # pending | approved | rejected | fulfilled
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    reviewer_notes = db.Column(db.Text)
    reviewed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship('Project', backref=db.backref('material_requests', lazy='dynamic'))
    requested_by = db.relationship('User', foreign_keys=[requested_by_id], backref='material_requests_made')
    reviewer = db.relationship('User', foreign_keys=[reviewer_id])

    @property
    def urgency_color(self):
        return {'low': 'secondary', 'normal': 'info', 'high': 'warning', 'urgent': 'danger'}.get(self.urgency, 'secondary')

    @property
    def urgency_label(self):
        return {'low': 'Χαμηλή', 'normal': 'Κανονική', 'high': 'Υψηλή', 'urgent': 'Επείγον'}.get(self.urgency, self.urgency)

    @property
    def status_label(self):
        return {'pending': 'Εκκρεμεί', 'approved': 'Εγκρίθηκε', 'rejected': 'Απορρίφθηκε', 'fulfilled': 'Εκτελέστηκε'}.get(self.status, self.status)

# ── TENDER DOCUMENTS (ΕΓΓΡΑΦΑ ΔΙΑΓΩΝΙΣΜΟΥ) ─────────────────────────────────
class TenderDocument(db.Model):
    __tablename__ = 'tender_documents'
    id = db.Column(db.Integer, primary_key=True)
    tender_id = db.Column(db.Integer, db.ForeignKey('tenders.id'), nullable=False)
    doc_type = db.Column(db.String(80), default='other')
    # proclamation | technical | financial | study | qualifications | other
    title = db.Column(db.String(400), nullable=False)
    file_path = db.Column(db.String(600))
    file_name = db.Column(db.String(400))
    extracted_text = db.Column(db.Text)  # cached PDF text for AI
    drive_file_id = db.Column(db.String(200))
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tender = db.relationship('Tender', backref=db.backref('documents_list', lazy='dynamic', cascade='all, delete-orphan'))
    uploaded_by = db.relationship('User', backref='uploaded_tender_docs')

    @property
    def type_label(self):
        return {
            'proclamation': 'Διακήρυξη', 'technical': 'Τεχνική Έκθεση/Μελέτη',
            'financial': 'Οικονομική Προσφορά', 'study': 'Τεχνική Περιγραφή',
            'qualifications': 'Δικαιολογητικά Συμμετοχής', 'other': 'Άλλο'
        }.get(self.doc_type, self.doc_type)


# ── INVOICE PAYMENTS (ΜΕΡΙΚΕΣ ΠΛΗΡΩΜΕΣ) ─────────────────────────────────────
class InvoicePayment(db.Model):
    __tablename__ = 'invoice_payments'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    payment_date = db.Column(db.Date, nullable=False, default=date.today)
    payment_method = db.Column(db.String(80))
    bank_account_id = db.Column(db.Integer, db.ForeignKey('bank_accounts.id'), nullable=True)
    reference = db.Column(db.String(300))  # αρ. εντολής, επιταγής κλπ
    notes = db.Column(db.Text)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    invoice = db.relationship('Invoice', backref=db.backref('payments', lazy='select'))
    bank_account = db.relationship('BankAccount', backref=db.backref('linked_payments', lazy='select'))
    created_by = db.relationship('User', backref='invoice_payments_made')


# ── PROJECT PAYMENT SCHEDULE (ΠΡΟΓΡΑΜΜΑ ΠΛΗΡΩΜΩΝ ΕΡΓΟΥ) ─────────────────────
class ProjectPayment(db.Model):
    __tablename__ = 'project_payments'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    title = db.Column(db.String(300), nullable=False)   # 'Προκαταβολή 30%', 'Α΄ Δόση'
    milestone = db.Column(db.String(400))               # τι πρέπει να γίνει για να πληρωθεί
    amount_expected = db.Column(db.Numeric(14, 2), nullable=False)
    amount_paid = db.Column(db.Numeric(14, 2), default=0)
    due_date = db.Column(db.Date)
    paid_date = db.Column(db.Date)
    status = db.Column(db.String(30), default='pending')  # pending | partial | paid | overdue
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship('Project', backref=db.backref('payment_schedule', lazy='dynamic', order_by='ProjectPayment.due_date'))
    invoice = db.relationship('Invoice', backref='project_payments')

    @property
    def remaining(self):
        return round(float(self.amount_expected) - float(self.amount_paid or 0), 2)

    @property
    def status_label(self):
        return {'pending': 'Εκκρεμεί', 'partial': 'Μερική Πληρωμή',
                'paid': 'Εξοφλήθηκε', 'overdue': 'Ληξιπρόθεσμο'}.get(self.status, self.status)

    @property
    def status_color(self):
        return {'pending': 'warning', 'partial': 'info', 'paid': 'success', 'overdue': 'danger'}.get(self.status, 'secondary')


# ── BANK ACCOUNTS / ΤΑΜΕΙΑΚΑ ΔΙΑΘΕΣΙΜΑ ──────────────────────────────────────
class BankAccount(db.Model):
    __tablename__ = 'bank_accounts'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)  # 'Πειραιώς Τρεχούμενος'
    bank_name = db.Column(db.String(150))
    iban = db.Column(db.String(34))
    account_number = db.Column(db.String(50))
    currency = db.Column(db.String(10), default='EUR')
    opening_balance = db.Column(db.Numeric(14, 2), default=0)
    opening_date = db.Column(db.Date, default=date.today)
    last_actual_balance = db.Column(db.Numeric(14, 2))   # manually entered from bank
    last_actual_date = db.Column(db.Date)
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def calculated_balance(self):
        """Expected balance = opening + all linked payments in/out."""
        base = float(self.opening_balance or 0)
        # Income payments credited to this account
        income = sum(
            float(p.amount) for p in self.linked_payments
            if p.invoice and p.invoice.invoice_type == 'income'
        )
        # Expense payments debited from this account
        expense = sum(
            float(p.amount) for p in self.linked_payments
            if p.invoice and p.invoice.invoice_type == 'expense'
        )
        return round(base + income - expense, 2)

    @property
    def discrepancy(self):
        if self.last_actual_balance is None:
            return None
        return round(float(self.last_actual_balance) - self.calculated_balance, 2)


# ── ΤΡΑΠΕΖΙΚΕΣ ΚΙΝΗΣΕΙΣ (BANK RECONCILIATION) ────────────────────────────────
class BankTransaction(db.Model):
    """Εισαγμένη τραπεζική κίνηση από αρχείο τράπεζας (CSV/Excel)."""
    __tablename__ = 'bank_transactions'

    id               = db.Column(db.Integer, primary_key=True)
    account_id       = db.Column(db.Integer, db.ForeignKey('bank_accounts.id'), nullable=False)
    transaction_date = db.Column(db.Date, nullable=False)
    value_date       = db.Column(db.Date)
    description      = db.Column(db.String(500), nullable=False)
    # positive = πίστωση (είσπραξη), negative = χρέωση (πληρωμή)
    amount           = db.Column(db.Numeric(12, 2), nullable=False)
    transaction_type = db.Column(db.String(30), default='other')
    # credit | debit | card | fee | transfer | other
    reference        = db.Column(db.String(200))   # αριθμός παραστατικού τράπεζας
    status           = db.Column(db.String(20), default='unmatched')
    # unmatched | matched | flagged | ignored
    matched_invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'))
    flag_reason      = db.Column(db.String(500))   # λόγος σήμανσης για τράπεζα
    notes            = db.Column(db.String(500))   # σημειώσεις χρήστη
    import_batch     = db.Column(db.String(200))   # όνομα αρχείου + timestamp εισαγωγής
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    account         = db.relationship('BankAccount',
                                      backref=db.backref('bank_transactions', lazy='dynamic'))
    matched_invoice = db.relationship('Invoice', foreign_keys=[matched_invoice_id])

    @property
    def is_credit(self):
        return float(self.amount or 0) > 0

    @property
    def abs_amount(self):
        return abs(float(self.amount or 0))

    @property
    def status_color(self):
        return {'unmatched': 'warning', 'matched': 'success',
                'flagged': 'danger', 'ignored': 'secondary'}.get(self.status, 'secondary')

    @property
    def status_label(self):
        return {'unmatched': 'Αταύτιστο', 'matched': 'Ταυτίστηκε',
                'flagged': 'Για Έρευνα', 'ignored': 'Αγνοήθηκε'}.get(self.status, self.status)

    @property
    def type_label(self):
        return {'credit': 'Πίστωση', 'debit': 'Χρέωση', 'card': 'Κάρτα',
                'fee': 'Χρέωση Τρ/ζας', 'transfer': 'Μεταφορά',
                'other': 'Άλλο'}.get(self.transaction_type, self.transaction_type)

    @property
    def type_icon(self):
        return {'credit': 'bi-arrow-down-circle-fill text-success',
                'debit':  'bi-arrow-up-circle-fill text-danger',
                'card':   'bi-credit-card-fill text-warning',
                'fee':    'bi-bank text-secondary',
                'transfer': 'bi-arrow-left-right text-info',
                'other':  'bi-circle text-muted'}.get(self.transaction_type, 'bi-circle text-muted')


# ── LEAVE REQUESTS (ΑΙΤΗΣΕΙΣ ΑΔΕΙΑΣ) ────────────────────────────────────────
class LeaveRequest(db.Model):
    __tablename__ = 'leave_requests'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    leave_type = db.Column(db.String(50), default='annual')
    # annual | sick | unpaid | maternity | study | other
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    working_days = db.Column(db.Integer)
    reason = db.Column(db.Text)
    status = db.Column(db.String(30), default='pending')  # pending | approved | rejected
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    review_notes = db.Column(db.Text)
    reviewed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    employee = db.relationship('Employee', backref=db.backref('leave_requests', lazy='dynamic'))
    reviewed_by = db.relationship('User', foreign_keys=[reviewed_by_id], backref='reviewed_leaves')

    @property
    def type_label(self):
        return {'annual': 'Κανονική Άδεια', 'sick': 'Ασθένεια', 'unpaid': 'Άδεια Άνευ Αποδοχών',
                'maternity': 'Μητρότητα/Πατρότητα', 'study': 'Εκπαιδευτική', 'other': 'Άλλη'
                }.get(self.leave_type, self.leave_type)

    @property
    def status_color(self):
        return {'pending': 'warning', 'approved': 'success', 'rejected': 'danger'}.get(self.status, 'secondary')


# ── LEAVE BALANCE (ΥΠΟΛΟΙΠΟ ΑΔΕΙΩΝ) ─────────────────────────────────────────
class LeaveBalance(db.Model):
    __tablename__ = 'leave_balances'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    total_days = db.Column(db.Integer, default=20)
    used_days = db.Column(db.Integer, default=0)

    employee = db.relationship('Employee', backref=db.backref('leave_balances', lazy='dynamic'))
    __table_args__ = (db.UniqueConstraint('employee_id', 'year', name='uq_leave_balance'),)

    @property
    def remaining_days(self):
        return max(0, (self.total_days or 0) - (self.used_days or 0))


# ── WORK LOG (ΩΡΕΣ ΕΡΓΑΣΙΑΣ) ─────────────────────────────────────────────────
class WorkLog(db.Model):
    __tablename__ = 'work_logs'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    work_date = db.Column(db.Date, nullable=False, default=date.today)
    hours = db.Column(db.Numeric(4, 1), default=8)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    employee = db.relationship('Employee', backref=db.backref('work_logs', lazy='dynamic'))
    project = db.relationship('Project', backref=db.backref('work_logs', lazy='dynamic'))


# ── INSURANCE POLICIES (ΑΣΦΑΛΙΣΤΗΡΙΑ) ────────────────────────────────────────
class InsurancePolicy(db.Model):
    __tablename__ = 'insurance_policies'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    policy_type = db.Column(db.String(80), default='other')
    # civil_liability | equipment | health | fire | accident | professional | vehicle | other
    insurance_company = db.Column(db.String(200))
    policy_number = db.Column(db.String(100))
    insured_object = db.Column(db.String(400))
    coverage_amount = db.Column(db.Numeric(14, 2))
    annual_premium = db.Column(db.Numeric(10, 2))
    payment_frequency = db.Column(db.String(30), default='annual')
    start_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date)
    status = db.Column(db.String(30), default='active')  # active | expired | cancelled
    auto_renew = db.Column(db.Boolean, default=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), nullable=True)
    file_path = db.Column(db.String(600))
    file_name = db.Column(db.String(400))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    vehicle = db.relationship('Vehicle', backref=db.backref('insurance_records', lazy='dynamic'))

    @property
    def days_to_expiry(self):
        if self.expiry_date:
            return (self.expiry_date - date.today()).days
        return None

    @property
    def type_label(self):
        return {
            'civil_liability': 'Αστική Ευθύνη Εργοταξίου', 'equipment': 'Εξοπλισμός',
            'health': 'Υγεία Εργαζομένων', 'fire': 'Πυρός', 'accident': 'Ατυχήματα',
            'professional': 'Επαγγελματική Ευθύνη', 'vehicle': 'Όχημα', 'other': 'Άλλο'
        }.get(self.policy_type, self.policy_type)

    @property
    def status_color(self):
        if self.days_to_expiry is None: return 'secondary'
        if self.days_to_expiry < 0: return 'danger'
        if self.days_to_expiry <= 30: return 'warning'
        return 'success'


# ── INVENTORY / ΑΠΟΘΗΚΗ ΥΛΙΚΩΝ ──────────────────────────────────────────────
class MaterialItem(db.Model):
    __tablename__ = 'material_items'
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(300), nullable=False)
    sku           = db.Column(db.String(100))
    category      = db.Column(db.String(150))  # chemical|tools|protective|consumable|other
    unit          = db.Column(db.String(50), default='τεμ.')
    current_stock = db.Column(db.Numeric(10, 3), default=0)
    min_stock     = db.Column(db.Numeric(10, 3), default=0)
    unit_price    = db.Column(db.Numeric(10, 2))
    supplier      = db.Column(db.String(300))
    location      = db.Column(db.String(200))
    notes         = db.Column(db.Text)
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def needs_reorder(self):
        if self.min_stock is not None and self.current_stock is not None:
            return float(self.current_stock) <= float(self.min_stock)
        return False

    @property
    def stock_value(self):
        if self.current_stock and self.unit_price:
            return round(float(self.current_stock) * float(self.unit_price), 2)
        return 0


class MaterialUsage(db.Model):
    __tablename__ = 'material_usages'
    id                  = db.Column(db.Integer, primary_key=True)
    material_id         = db.Column(db.Integer, db.ForeignKey('material_items.id'), nullable=False)
    project_id          = db.Column(db.Integer, db.ForeignKey('projects.id'))
    quantity            = db.Column(db.Numeric(10, 3), nullable=False)
    unit_price_snapshot = db.Column(db.Numeric(10, 2))
    used_by_id          = db.Column(db.Integer, db.ForeignKey('users.id'))
    used_at             = db.Column(db.Date, default=date.today)
    notes               = db.Column(db.String(500))
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)

    material = db.relationship('MaterialItem', backref=db.backref('usages', lazy='dynamic'))
    project  = db.relationship('Project',      backref=db.backref('material_usages', lazy='dynamic'))
    used_by  = db.relationship('User', foreign_keys=[used_by_id])

    @property
    def line_cost(self):
        price = self.unit_price_snapshot or (self.material.unit_price if self.material else None)
        if price and self.quantity:
            return round(float(price) * float(self.quantity), 2)
        return 0


# ── PAYROLL / ΜΙΣΘΟΔΟΣΙΑ ────────────────────────────────────────────────────
class PayrollRecord(db.Model):
    __tablename__ = 'payroll_records'
    id                = db.Column(db.Integer, primary_key=True)
    employee_id       = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    month             = db.Column(db.Integer, nullable=False)
    year              = db.Column(db.Integer, nullable=False)
    gross_salary      = db.Column(db.Numeric(10, 2), nullable=False)
    ika_employee_rate = db.Column(db.Numeric(5, 2), default=13.87)
    ika_employer_rate = db.Column(db.Numeric(5, 2), default=24.56)
    ika_employee      = db.Column(db.Numeric(10, 2))
    ika_employer      = db.Column(db.Numeric(10, 2))
    tax_withheld      = db.Column(db.Numeric(10, 2), default=0)
    other_deductions  = db.Column(db.Numeric(10, 2), default=0)
    net_salary        = db.Column(db.Numeric(10, 2))
    days_worked       = db.Column(db.Integer, default=25)
    days_absent       = db.Column(db.Integer, default=0)
    status            = db.Column(db.String(30), default='draft')  # draft|approved|paid
    paid_date         = db.Column(db.Date)
    bank_account_id   = db.Column(db.Integer, db.ForeignKey('bank_accounts.id'), nullable=True)
    notes             = db.Column(db.Text)
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)

    employee     = db.relationship('Employee',    backref=db.backref('payroll_records', lazy='dynamic'))
    bank_account = db.relationship('BankAccount', foreign_keys=[bank_account_id])

    __table_args__ = (db.UniqueConstraint('employee_id', 'month', 'year', name='_emp_month_year_uc'),)

    @property
    def total_employer_cost(self):
        return round(float(self.gross_salary or 0) + float(self.ika_employer or 0), 2)

    @property
    def month_label(self):
        m = ['','Ιανουάριος','Φεβρουάριος','Μάρτιος','Απρίλιος','Μάιος','Ιούνιος',
             'Ιούλιος','Αύγουστος','Σεπτέμβριος','Οκτώβριος','Νοέμβριος','Δεκέμβριος']
        return m[self.month] if 1 <= self.month <= 12 else str(self.month)

    @property
    def status_color(self):
        return {'draft':'secondary','approved':'primary','paid':'success'}.get(self.status,'secondary')


# ── PROJECT PHOTOS / ΦΩΤΟΓΡΑΦΙΚΟ ΑΡΧΕΙΟ ─────────────────────────────────────
class ProjectPhoto(db.Model):
    __tablename__ = 'project_photos'
    id             = db.Column(db.Integer, primary_key=True)
    project_id     = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    phase_id       = db.Column(db.Integer, db.ForeignKey('project_phases.id'), nullable=True)
    file_path      = db.Column(db.String(600), nullable=False)
    file_name      = db.Column(db.String(400))
    photo_type     = db.Column(db.String(50), default='during')  # before|during|after|detail
    description    = db.Column(db.String(500))
    taken_at       = db.Column(db.Date)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    project     = db.relationship('Project',      backref=db.backref('photos', lazy='dynamic'))
    phase       = db.relationship('ProjectPhase', backref=db.backref('photos', lazy='dynamic'))
    uploaded_by = db.relationship('User', foreign_keys=[uploaded_by_id])

    @property
    def type_label(self):
        return {'before':'Πριν','during':'Κατά τη Διάρκεια','after':'Μετά','detail':'Λεπτομέρεια'}.get(self.photo_type, self.photo_type)

    @property
    def type_color(self):
        return {'before':'danger','during':'warning','after':'success','detail':'info'}.get(self.photo_type,'secondary')


# ── QUOTES / ΠΡΟΣΦΟΡΕΣ ───────────────────────────────────────────────────────
class Quote(db.Model):
    __tablename__ = 'quotes'
    id                   = db.Column(db.Integer, primary_key=True)
    title                = db.Column(db.String(400), nullable=False)
    client_name          = db.Column(db.String(300))
    client_email         = db.Column(db.String(200))
    client_phone         = db.Column(db.String(50))
    client_afm           = db.Column(db.String(20))
    issue_date           = db.Column(db.Date)
    valid_until          = db.Column(db.Date)
    status               = db.Column(db.String(30), default='draft')  # draft|sent|accepted|rejected|expired
    tender_id            = db.Column(db.Integer, db.ForeignKey('tenders.id'), nullable=True)
    converted_project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    notes                = db.Column(db.Text)
    terms                = db.Column(db.Text)
    created_by_id        = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at           = db.Column(db.DateTime, default=datetime.utcnow)

    tender            = db.relationship('Tender',  backref=db.backref('quotes', lazy='dynamic'))
    converted_project = db.relationship('Project', foreign_keys=[converted_project_id], backref='source_quote')
    created_by        = db.relationship('User',    foreign_keys=[created_by_id])

    @property
    def subtotal(self):
        return round(sum(float(i.line_total) for i in self.items), 2)

    @property
    def vat_total(self):
        return round(sum(float(i.vat_amount) for i in self.items), 2)

    @property
    def grand_total(self):
        return round(self.subtotal + self.vat_total, 2)

    @property
    def status_label(self):
        return {'draft':'Πρόχειρο','sent':'Εστάλη','accepted':'Εγκρίθηκε',
                'rejected':'Απορρίφθηκε','expired':'Έληξε'}.get(self.status, self.status)

    @property
    def status_color(self):
        return {'draft':'secondary','sent':'primary','accepted':'success',
                'rejected':'danger','expired':'warning'}.get(self.status,'secondary')

    @property
    def is_expired(self):
        return self.valid_until and self.valid_until < date.today() and self.status not in ('accepted','rejected')


class QuoteItem(db.Model):
    __tablename__ = 'quote_items'
    id          = db.Column(db.Integer, primary_key=True)
    quote_id    = db.Column(db.Integer, db.ForeignKey('quotes.id', ondelete='CASCADE'), nullable=False)
    description = db.Column(db.String(600), nullable=False)
    unit        = db.Column(db.String(50), default='τεμ.')
    quantity    = db.Column(db.Numeric(10, 3), default=1)
    unit_price  = db.Column(db.Numeric(12, 2), nullable=False)
    vat_rate    = db.Column(db.Numeric(5, 2), default=24)
    sort_order  = db.Column(db.Integer, default=0)

    quote = db.relationship('Quote', backref=db.backref('items', lazy='select',
                            cascade='all, delete-orphan', order_by='QuoteItem.sort_order'))

    @property
    def line_total(self):
        return round(float(self.quantity or 1) * float(self.unit_price or 0), 2)

    @property
    def vat_amount(self):
        return round(self.line_total * float(self.vat_rate or 0) / 100, 2)


# ── SAFETY EQUIPMENT / ΜΑΠ ──────────────────────────────────────────────────
class SafetyEquipment(db.Model):
    __tablename__ = 'safety_equipment'
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(300), nullable=False)
    category      = db.Column(db.String(100))  # helmet|gloves|harness|boots|vest|mask|goggles|other
    serial_number = db.Column(db.String(100))
    purchase_date = db.Column(db.Date)
    expiry_date   = db.Column(db.Date)
    condition     = db.Column(db.String(50), default='good')  # good|fair|poor|retired
    notes         = db.Column(db.Text)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def days_to_expiry(self):
        return (self.expiry_date - date.today()).days if self.expiry_date else None

    @property
    def current_assignment(self):
        return self.assignments.filter_by(returned_date=None).first()

    @property
    def is_assigned(self):
        return self.current_assignment is not None

    @property
    def category_label(self):
        return {'helmet':'Κράνος','gloves':'Γάντια','harness':'Ζώνη','boots':'Μπότες',
                'vest':'Γιλέκο','mask':'Μάσκα','goggles':'Γυαλιά','other':'Άλλο'}.get(self.category, self.category or '—')


class PPEAssignment(db.Model):
    __tablename__ = 'ppe_assignments'
    id            = db.Column(db.Integer, primary_key=True)
    equipment_id  = db.Column(db.Integer, db.ForeignKey('safety_equipment.id'), nullable=False)
    employee_id   = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    assigned_date = db.Column(db.Date, default=date.today)
    returned_date = db.Column(db.Date)
    notes         = db.Column(db.String(500))
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    equipment = db.relationship('SafetyEquipment', backref=db.backref('assignments', lazy='dynamic'))
    employee  = db.relationship('Employee',         backref=db.backref('ppe_assignments', lazy='dynamic'))


# ── SUPPLIES MONTHLY SUMMARY (Pylon sync) ────────────────────────────────────
class SuppliesMonthlySummary(db.Model):
    """Manual monthly entry from Pylon export — εμπορικό τμήμα ART RESTORATION SUPPLIES."""
    __tablename__ = 'supplies_monthly_summary'
    __table_args__ = (db.UniqueConstraint('month', 'year', name='uq_supplies_month_year'),)

    id              = db.Column(db.Integer, primary_key=True)
    month           = db.Column(db.Integer, nullable=False)   # 1–12
    year            = db.Column(db.Integer, nullable=False)
    # Έσοδα
    revenue_net     = db.Column(db.Numeric(12, 2), default=0)  # καθαρός τζίρος
    revenue_vat     = db.Column(db.Numeric(12, 2), default=0)  # ΦΠΑ εσόδων
    # Αγορές / κόστος πωληθέντων
    purchases_net   = db.Column(db.Numeric(12, 2), default=0)  # αγορές καθαρές
    purchases_vat   = db.Column(db.Numeric(12, 2), default=0)  # ΦΠΑ αγορών
    # Επιστροφές
    returns_net     = db.Column(db.Numeric(12, 2), default=0)
    # Μεταδεδομένα
    notes           = db.Column(db.String(500))
    entered_by_id   = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    entered_by = db.relationship('User', foreign_keys=[entered_by_id])

    @property
    def gross_profit(self):
        return float(self.revenue_net or 0) - float(self.purchases_net or 0) - float(self.returns_net or 0)

    @property
    def net_vat(self):
        return float(self.revenue_vat or 0) - float(self.purchases_vat or 0)

    @property
    def month_label(self):
        return ['', 'Ιανουάριος', 'Φεβρουάριος', 'Μάρτιος', 'Απρίλιος', 'Μάιος',
                'Ιούνιος', 'Ιούλιος', 'Αύγουστος', 'Σεπτέμβριος', 'Οκτώβριος',
                'Νοέμβριος', 'Δεκέμβριος'][self.month]


# ── ΥΠΕΡΓΟΛΑΒΟΙ ──────────────────────────────────────────────────────────────

class Subcontractor(db.Model):
    __tablename__ = 'subcontractors'
    id              = db.Column(db.Integer, primary_key=True)
    company_name    = db.Column(db.String(200), nullable=False)
    afm             = db.Column(db.String(20))
    contact_name    = db.Column(db.String(150))
    phone           = db.Column(db.String(30))
    email           = db.Column(db.String(150))
    address         = db.Column(db.String(300))
    specialty       = db.Column(db.String(100))   # scaffolding|electrical|cleaning|transport|other
    insurance_number = db.Column(db.String(100))
    insurance_expiry = db.Column(db.Date)
    rating          = db.Column(db.Integer, default=3)  # 1–5
    notes           = db.Column(db.Text)
    is_active       = db.Column(db.Boolean, default=True)
    # Portal access
    portal_username = db.Column(db.String(80), unique=True)
    portal_password_hash = db.Column(db.String(256))
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    def set_portal_password(self, password):
        from werkzeug.security import generate_password_hash
        self.portal_password_hash = generate_password_hash(password)

    def check_portal_password(self, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.portal_password_hash, password)

    @property
    def insurance_ok(self):
        if not self.insurance_expiry: return None
        return self.insurance_expiry >= date.today()

    @property
    def specialty_label(self):
        return {
            'conservator':       'Συντηρητής Αρχαιοτήτων',
            'conservator_paper': 'Συντηρητής Χαρτιού/Βιβλίων',
            'conservator_wood':  'Συντηρητής Ξύλου/Επίπλων',
            'conservator_stone': 'Συντηρητής Λίθου/Τοιχογραφιών',
            'conservator_metal': 'Συντηρητής Μετάλλων',
            'showcases':         'Προθήκες/Εξοπλισμός Έκθεσης',
            'lighting':          'Φωτισμός Χώρων',
            'electrical':        'Ηλεκτρολογικά',
            'cleaning':          'Καθαρισμός',
            'transport':         'Μεταφορές/Συσκευασία',
            'security':          'Συστήματα Ασφαλείας',
            'other':             'Άλλο',
        }.get(self.specialty or '', self.specialty or '—')


class SubcontractorContract(db.Model):
    __tablename__ = 'subcontractor_contracts'
    id                = db.Column(db.Integer, primary_key=True)
    subcontractor_id  = db.Column(db.Integer, db.ForeignKey('subcontractors.id'), nullable=False)
    project_id        = db.Column(db.Integer, db.ForeignKey('projects.id'))
    title             = db.Column(db.String(300), nullable=False)
    scope_of_work     = db.Column(db.Text)
    contract_value    = db.Column(db.Numeric(12, 2), default=0)
    payment_terms     = db.Column(db.String(200))
    start_date        = db.Column(db.Date)
    end_date          = db.Column(db.Date)
    status            = db.Column(db.String(30), default='draft')
    # draft|signed|active|completed|terminated
    contract_file_path = db.Column(db.String(600))
    notes             = db.Column(db.Text)
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)

    subcontractor = db.relationship('Subcontractor', backref=db.backref('contracts', lazy='dynamic'))
    project       = db.relationship('Project',       backref=db.backref('subcontractor_contracts', lazy='dynamic'))

    @property
    def status_label(self):
        return {'draft':'Πρόχειρο','signed':'Υπογεγραμμένο','active':'Ενεργό',
                'completed':'Ολοκληρώθηκε','terminated':'Ακυρώθηκε'}.get(self.status, self.status)

    @property
    def status_color(self):
        return {'draft':'secondary','signed':'info','active':'success',
                'completed':'primary','terminated':'danger'}.get(self.status, 'secondary')

    @property
    def total_paid(self):
        return sum(float(i.amount_net or 0) for i in self.invoices if i.status == 'paid')

    @property
    def balance(self):
        return float(self.contract_value or 0) - self.total_paid


class SubcontractorWorkLog(db.Model):
    """Ημερήσια αναφορά από τον υπεργολάβο μέσω portal."""
    __tablename__ = 'subcontractor_work_logs'
    id              = db.Column(db.Integer, primary_key=True)
    contract_id     = db.Column(db.Integer, db.ForeignKey('subcontractor_contracts.id'), nullable=False)
    log_date        = db.Column(db.Date, nullable=False, default=date.today)
    work_description = db.Column(db.Text, nullable=False)
    workers_count   = db.Column(db.Integer, default=1)
    hours_worked    = db.Column(db.Numeric(5, 1), default=8)
    completion_pct  = db.Column(db.Integer, default=0)  # 0–100
    issues          = db.Column(db.Text)
    status          = db.Column(db.String(20), default='pending')  # pending|approved|rejected
    reviewed_by_id  = db.Column(db.Integer, db.ForeignKey('users.id'))
    reviewed_at     = db.Column(db.DateTime)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    contract    = db.relationship('SubcontractorContract', backref=db.backref('work_logs', lazy='dynamic'))
    reviewed_by = db.relationship('User', foreign_keys=[reviewed_by_id])

    @property
    def status_color(self):
        return {'pending':'warning','approved':'success','rejected':'danger'}.get(self.status,'secondary')


class SubcontractorInvoice(db.Model):
    """Τιμολόγιο που εκδίδει ο υπεργολάβος προς ART RESTORATION."""
    __tablename__ = 'subcontractor_invoices'
    id              = db.Column(db.Integer, primary_key=True)
    contract_id     = db.Column(db.Integer, db.ForeignKey('subcontractor_contracts.id'), nullable=False)
    invoice_number  = db.Column(db.String(60))
    invoice_date    = db.Column(db.Date)
    period_from     = db.Column(db.Date)
    period_to       = db.Column(db.Date)
    amount_net      = db.Column(db.Numeric(12, 2), default=0)
    vat_rate        = db.Column(db.Numeric(5, 2), default=24)
    vat_amount      = db.Column(db.Numeric(12, 2), default=0)
    total_amount    = db.Column(db.Numeric(12, 2), default=0)
    status          = db.Column(db.String(20), default='pending')  # pending|approved|paid
    paid_date       = db.Column(db.Date)
    file_path       = db.Column(db.String(600))
    notes           = db.Column(db.String(500))
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    contract = db.relationship('SubcontractorContract', backref=db.backref('invoices', lazy='dynamic'))

    @property
    def status_color(self):
        return {'pending':'warning','approved':'info','paid':'success'}.get(self.status,'secondary')

    @property
    def status_label(self):
        return {'pending':'Εκκρεμεί','approved':'Εγκρίθηκε','paid':'Πληρώθηκε'}.get(self.status, self.status)


# ── ΔΙΚΑΙΟΛΟΓΗΤΙΚΑ ΥΠΕΡΓΟΛΑΒΟΥ ───────────────────────────────────────────────
class SubcontractorDocument(db.Model):
    """Δικαιολογητικά εταιρείας υπεργολάβου (ασφάλεια, άδειες, φορολογική ενημερότητα κλπ)."""
    __tablename__ = 'subcontractor_documents'

    DOC_TYPES = [
        ('insurance',        'Ασφαλιστήριο Συμβόλαιο'),
        ('tax_clearance',    'Φορολογική Ενημερότητα'),
        ('asep_clearance',   'Ασφαλιστική Ενημερότητα (ΕΦΚΑ)'),
        ('professional_license', 'Άδεια Επαγγέλματος Εταιρείας'),
        ('company_statute',  'Καταστατικό / ΦΕΚ'),
        ('iso_cert',         'Πιστοποίηση ISO / Ποιότητας'),
        ('other',            'Άλλο Δικαιολογητικό'),
    ]

    id               = db.Column(db.Integer, primary_key=True)
    subcontractor_id = db.Column(db.Integer, db.ForeignKey('subcontractors.id'), nullable=False)
    doc_type         = db.Column(db.String(50), nullable=False, default='other')
    title            = db.Column(db.String(300), nullable=False)
    file_path        = db.Column(db.String(600))
    file_name        = db.Column(db.String(300))
    issue_date       = db.Column(db.Date)
    expiry_date      = db.Column(db.Date)
    notes            = db.Column(db.String(500))
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    subcontractor = db.relationship('Subcontractor',
                                    backref=db.backref('documents', lazy='dynamic',
                                                       order_by='SubcontractorDocument.expiry_date'))

    @property
    def doc_type_label(self):
        return dict(self.DOC_TYPES).get(self.doc_type, self.doc_type)

    @property
    def days_to_expiry(self):
        if not self.expiry_date:
            return None
        return (self.expiry_date - date.today()).days

    @property
    def expiry_status(self):
        d = self.days_to_expiry
        if d is None:    return 'none'
        if d < 0:        return 'expired'
        if d <= 30:      return 'expiring'
        return 'valid'

    @property
    def expiry_color(self):
        return {'expired': 'danger', 'expiring': 'warning', 'valid': 'success', 'none': 'secondary'}.get(self.expiry_status, 'secondary')

    @property
    def expiry_label(self):
        d = self.days_to_expiry
        if d is None:  return '—'
        if d < 0:      return f'Έληξε {abs(d)} ημ. πριν'
        if d == 0:     return 'Λήγει ΣΗΜΕΡΑ'
        if d <= 30:    return f'Λήγει σε {d} ημ.'
        return self.expiry_date.strftime('%d/%m/%Y')


# ── ΠΡΟΣΩΠΙΚΟ ΥΠΕΡΓΟΛΑΒΟΥ ────────────────────────────────────────────────────
class SubcontractorPersonnel(db.Model):
    """Εργαζόμενοι/τεχνίτες που δηλώνει ο υπεργολάβος μέσω portal."""
    __tablename__ = 'subcontractor_personnel'

    ROLES = [
        ('supervisor',     'Επιστάτης / Υπεύθυνος Έργου'),
        ('conservator',    'Συντηρητής'),
        ('technician',     'Τεχνίτης'),
        ('electrician',    'Ηλεκτρολόγος'),
        ('laborer',        'Εργάτης'),
        ('driver',         'Οδηγός'),
        ('other',          'Άλλο'),
    ]

    id               = db.Column(db.Integer, primary_key=True)
    subcontractor_id = db.Column(db.Integer, db.ForeignKey('subcontractors.id'), nullable=False)
    full_name        = db.Column(db.String(200), nullable=False)
    role             = db.Column(db.String(50), default='technician')
    license_type     = db.Column(db.String(200))   # π.χ. "Άδεια Α' τάξης Συντηρητή"
    license_number   = db.Column(db.String(100))
    license_expiry   = db.Column(db.Date)
    license_file_path = db.Column(db.String(600))
    is_active        = db.Column(db.Boolean, default=True)
    notes            = db.Column(db.String(500))
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    subcontractor = db.relationship('Subcontractor',
                                    backref=db.backref('personnel', lazy='dynamic',
                                                       order_by='SubcontractorPersonnel.full_name'))

    @property
    def role_label(self):
        return dict(self.ROLES).get(self.role, self.role)

    @property
    def license_days_to_expiry(self):
        if not self.license_expiry: return None
        return (self.license_expiry - date.today()).days

    @property
    def license_status(self):
        d = self.license_days_to_expiry
        if d is None: return 'none'
        if d < 0:     return 'expired'
        if d <= 30:   return 'expiring'
        return 'valid'

    @property
    def license_color(self):
        return {'expired':'danger','expiring':'warning','valid':'success','none':'secondary'}.get(self.license_status,'secondary')


# ── ΚΟΙΝΟΧΡΗΣΤΑ ΕΓΓΡΑΦΑ ΕΡΓΟΥ (για portal υπεργολάβου) ──────────────────────
class ProjectSharedDocument(db.Model):
    """Έγγραφο έργου που κοινοποιεί η εταιρεία στον υπεργολάβο μέσω portal."""
    __tablename__ = 'project_shared_documents'

    id               = db.Column(db.Integer, primary_key=True)
    project_id       = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    subcontractor_id = db.Column(db.Integer, db.ForeignKey('subcontractors.id'), nullable=False)
    title            = db.Column(db.String(300), nullable=False)
    description      = db.Column(db.String(500))
    file_path        = db.Column(db.String(600))
    file_name        = db.Column(db.String(300))
    doc_category     = db.Column(db.String(50), default='other')
    # study|drawing|specification|contract|permit|other
    shared_by_id     = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    project       = db.relationship('Project', backref=db.backref('shared_documents', lazy='dynamic'))
    subcontractor = db.relationship('Subcontractor', backref=db.backref('shared_documents', lazy='dynamic'))
    shared_by     = db.relationship('User', foreign_keys=[shared_by_id])

    @property
    def category_label(self):
        return {'study':'Μελέτη','drawing':'Σχέδιο','specification':'Τεχνικές Προδιαγραφές',
                'contract':'Σύμβαση','permit':'Άδεια','other':'Άλλο'}.get(self.doc_category,'Άλλο')

    @property
    def category_icon(self):
        return {'study':'bi-book','drawing':'bi-rulers','specification':'bi-file-text',
                'contract':'bi-pen','permit':'bi-shield-check','other':'bi-file'}.get(self.doc_category,'bi-file')


# ── ΕΠΙΜΕΤΡΗΣΕΙΣ ΥΠΕΡΓΟΛΑΒΟΥ ─────────────────────────────────────────────────
class SubcontractorMeasurement(db.Model):
    """Επιμέτρηση εργασιών — υποβάλλει ο υπεργολάβος, εγκρίνει η εταιρεία."""
    __tablename__ = 'subcontractor_measurements'

    id          = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey('subcontractor_contracts.id'), nullable=False)
    phase_id    = db.Column(db.Integer, db.ForeignKey('project_phases.id'))
    title       = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    quantity    = db.Column(db.Numeric(10, 3), default=0)
    unit        = db.Column(db.String(30), default='τ.μ.')
    unit_price  = db.Column(db.Numeric(10, 2), default=0)
    total_amount = db.Column(db.Numeric(12, 2), default=0)
    measurement_date = db.Column(db.Date, default=date.today)
    status      = db.Column(db.String(20), default='pending')
    # pending | approved | rejected | paid
    approved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_at  = db.Column(db.DateTime)
    rejection_reason = db.Column(db.String(500))
    linked_invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'))
    file_path   = db.Column(db.String(600))   # φωτογραφίες / έγγραφο επιμέτρησης
    notes       = db.Column(db.String(500))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    contract       = db.relationship('SubcontractorContract',
                                     backref=db.backref('measurements', lazy='dynamic'))
    phase          = db.relationship('ProjectPhase', foreign_keys=[phase_id])
    approved_by    = db.relationship('User', foreign_keys=[approved_by_id])
    linked_invoice = db.relationship('Invoice', foreign_keys=[linked_invoice_id])

    @property
    def status_label(self):
        return {'pending':'Αναμονή Έγκρισης','approved':'Εγκρίθηκε',
                'rejected':'Απορρίφθηκε','paid':'Πληρώθηκε'}.get(self.status, self.status)

    @property
    def status_color(self):
        return {'pending':'warning','approved':'success','rejected':'danger','paid':'primary'}.get(self.status,'secondary')


# ── ΣΚΑΛΩΣΙΕΣ ────────────────────────────────────────────────────────────────

class ScaffoldingItem(db.Model):
    """Εξαρτήματα σκαλωσιάς που ανήκουν στην εταιρεία."""
    __tablename__ = 'scaffolding_items'
    id             = db.Column(db.Integer, primary_key=True)
    item_type      = db.Column(db.String(50), nullable=False)  # frame|panel|tube|coupler|jack|plank|net|other
    code           = db.Column(db.String(60))
    description    = db.Column(db.String(300))
    quantity_owned = db.Column(db.Integer, default=0)
    condition      = db.Column(db.String(30), default='good')  # good|fair|damaged|retired
    purchase_date  = db.Column(db.Date)
    purchase_price = db.Column(db.Numeric(10, 2))
    location       = db.Column(db.String(200))
    notes          = db.Column(db.Text)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def type_label(self):
        return {'frame':'Πλαίσιο','panel':'Πάνελ','tube':'Σωλήνας','coupler':'Σύνδεσμος',
                'jack':'Γρύλος','plank':'Σανίδα','net':'Δίχτυ','other':'Άλλο'}.get(self.item_type, self.item_type)

    @property
    def quantity_deployed(self):
        return sum(
            line.quantity for a in self.assignment_lines
            if a.scaffolding_assignment.status == 'deployed'
            for line in [a]
        )

    @property
    def quantity_available(self):
        deployed = db.session.query(
            db.func.sum(ScaffoldingAssignmentLine.quantity)
        ).join(ScaffoldingAssignment).filter(
            ScaffoldingAssignmentLine.item_id == self.id,
            ScaffoldingAssignment.status == 'deployed'
        ).scalar() or 0
        return self.quantity_owned - int(deployed)


class ScaffoldingAssignment(db.Model):
    """Ανάθεση σκαλωσιάς σε έργο."""
    __tablename__ = 'scaffolding_assignments'
    id              = db.Column(db.Integer, primary_key=True)
    project_id      = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    date_out        = db.Column(db.Date, nullable=False, default=date.today)
    date_in_expected = db.Column(db.Date)
    date_returned   = db.Column(db.Date)
    # Κόστος (αν νοικιάζεται εξωτερικά)
    is_rented       = db.Column(db.Boolean, default=False)
    rental_supplier = db.Column(db.String(200))
    daily_rental_cost = db.Column(db.Numeric(8, 2), default=0)
    # Εγκατάσταση
    assembly_by     = db.Column(db.String(30), default='internal')  # internal|subcontractor
    assembly_subcontractor_id = db.Column(db.Integer, db.ForeignKey('subcontractors.id'))
    status          = db.Column(db.String(30), default='deployed')  # deployed|partial_return|returned
    notes           = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    project                = db.relationship('Project',        backref=db.backref('scaffolding_assignments', lazy='dynamic'))
    assembly_subcontractor = db.relationship('Subcontractor',  foreign_keys=[assembly_subcontractor_id])

    @property
    def days_deployed(self):
        end = self.date_returned or date.today()
        return (end - self.date_out).days if self.date_out else 0

    @property
    def rental_cost_total(self):
        if not self.is_rented or not self.daily_rental_cost: return 0
        return float(self.daily_rental_cost) * self.days_deployed

    @property
    def status_label(self):
        return {'deployed':'Σε χρήση','partial_return':'Μερική Επιστροφή',
                'returned':'Επεστράφη'}.get(self.status, self.status)

    @property
    def status_color(self):
        return {'deployed':'success','partial_return':'warning','returned':'secondary'}.get(self.status,'secondary')


class ScaffoldingAssignmentLine(db.Model):
    """Γραμμή ανάθεσης: ποιο εξάρτημα και πόσα."""
    __tablename__ = 'scaffolding_assignment_lines'
    id             = db.Column(db.Integer, primary_key=True)
    assignment_id  = db.Column(db.Integer, db.ForeignKey('scaffolding_assignments.id'), nullable=False)
    item_id        = db.Column(db.Integer, db.ForeignKey('scaffolding_items.id'), nullable=False)
    quantity       = db.Column(db.Integer, default=1)

    scaffolding_assignment = db.relationship('ScaffoldingAssignment', backref=db.backref('lines', lazy='dynamic'))
    item                   = db.relationship('ScaffoldingItem',        backref=db.backref('assignment_lines', lazy='dynamic'))


class ScaffoldingInspection(db.Model):
    """Έλεγχος ασφάλειας σκαλωσιάς."""
    __tablename__ = 'scaffolding_inspections'
    id              = db.Column(db.Integer, primary_key=True)
    assignment_id   = db.Column(db.Integer, db.ForeignKey('scaffolding_assignments.id'), nullable=False)
    inspection_date = db.Column(db.Date, nullable=False, default=date.today)
    inspector_id    = db.Column(db.Integer, db.ForeignKey('employees.id'))
    result          = db.Column(db.String(20), default='pass')  # pass|fail|conditional
    notes           = db.Column(db.Text)
    next_inspection = db.Column(db.Date)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    assignment = db.relationship('ScaffoldingAssignment', backref=db.backref('inspections', lazy='dynamic'))
    inspector  = db.relationship('Employee', foreign_keys=[inspector_id])

    @property
    def result_color(self):
        return {'pass':'success','fail':'danger','conditional':'warning'}.get(self.result,'secondary')

# ── ΣΧΕΔΙΑΣΜΟΣ ────────────────────────────────────────────────────────────────

class DesignProject(db.Model):
    """Μελέτη / Σχεδιασμός που συνδέεται (προαιρετικά) με ένα έργο."""
    __tablename__ = 'design_projects'
    id             = db.Column(db.Integer, primary_key=True)
    project_id     = db.Column(db.Integer, db.ForeignKey('projects.id'))
    title          = db.Column(db.String(300), nullable=False)
    design_type    = db.Column(db.String(60), default='architectural')
    # architectural|structural|electrical|mechanical|interior|color_scheme|other
    description    = db.Column(db.Text)
    client_brief   = db.Column(db.Text)       # Εντολή πελάτη
    status         = db.Column(db.String(30), default='draft')
    # draft|in_design|in_review|approved|rejected|final
    priority       = db.Column(db.String(20), default='normal')  # low|normal|high|urgent
    designer_id    = db.Column(db.Integer, db.ForeignKey('employees.id'))
    assigned_sub_id = db.Column(db.Integer, db.ForeignKey('subcontractors.id'))
    # External designer / sub if not internal
    deadline       = db.Column(db.Date)
    approved_date  = db.Column(db.Date)
    budget         = db.Column(db.Numeric(10, 2), default=0)  # Εκτιμώμενο κόστος
    actual_cost    = db.Column(db.Numeric(10, 2), default=0)  # Πραγματικό κόστος
    notes          = db.Column(db.Text)
    created_by_id  = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project      = db.relationship('Project',       backref=db.backref('design_projects', lazy='dynamic'))
    designer     = db.relationship('Employee',      foreign_keys=[designer_id])
    assigned_sub = db.relationship('Subcontractor', foreign_keys=[assigned_sub_id])
    created_by   = db.relationship('User',          foreign_keys=[created_by_id])

    @property
    def status_label(self):
        return {
            'draft':     'Πρόχειρο',
            'in_design': 'Σε Εξέλιξη',
            'in_review': 'Προς Έγκριση',
            'approved':  'Εγκρίθηκε',
            'rejected':  'Απορρίφθηκε',
            'final':     'Οριστικοποιήθηκε',
        }.get(self.status, self.status)

    @property
    def status_color(self):
        return {
            'draft':     'secondary',
            'in_design': 'warning',
            'in_review': 'info',
            'approved':  'success',
            'rejected':  'danger',
            'final':     'primary',
        }.get(self.status, 'secondary')

    @property
    def priority_color(self):
        return {'low':'secondary','normal':'info','high':'warning','urgent':'danger'}.get(self.priority,'secondary')

    @property
    def type_label(self):
        return {
            'architectural': 'Αρχιτεκτονική',
            'structural':    'Στατική',
            'electrical':    'Ηλεκτρολογική',
            'mechanical':    'Μηχανολογική',
            'interior':      'Εσωτερικός Χώρος',
            'color_scheme':  'Χρωματολόγιο',
            'other':         'Άλλο',
        }.get(self.design_type, self.design_type)

    @property
    def latest_revision(self):
        revs = self.revisions.order_by(DesignRevision.version_number.desc()).first()
        return revs

    @property
    def revision_count(self):
        return self.revisions.count()


class DesignRevision(db.Model):
    """Έκδοση / αναθεώρηση μελέτης."""
    __tablename__ = 'design_revisions'
    id             = db.Column(db.Integer, primary_key=True)
    design_id      = db.Column(db.Integer, db.ForeignKey('design_projects.id'), nullable=False)
    version_number = db.Column(db.Integer, default=1)
    title          = db.Column(db.String(200))        # π.χ. "Αρχική Πρόταση", "Μετά Παρατηρήσεις"
    description    = db.Column(db.Text)               # Τι άλλαξε
    file_path      = db.Column(db.String(600))        # Αρχείο σχεδίου
    file_name      = db.Column(db.String(200))
    submitted_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    reviewed_by_id  = db.Column(db.Integer, db.ForeignKey('users.id'))
    review_notes    = db.Column(db.Text)              # Παρατηρήσεις αναθεωρητή
    status          = db.Column(db.String(20), default='pending')
    # pending|approved|rejected
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    design       = db.relationship('DesignProject', backref=db.backref('revisions', lazy='dynamic'))
    submitted_by = db.relationship('User', foreign_keys=[submitted_by_id])
    reviewed_by  = db.relationship('User', foreign_keys=[reviewed_by_id])

    @property
    def status_color(self):
        return {'pending':'warning','approved':'success','rejected':'danger'}.get(self.status,'secondary')

    @property
    def status_label(self):
        return {'pending':'Σε Αναμονή','approved':'Εγκρίθηκε','rejected':'Απορρίφθηκε'}.get(self.status, self.status)
