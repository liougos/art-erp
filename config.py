import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'art-restoration-erp-secret-2026')

    # Railway/Render provide postgres:// but SQLAlchemy 2.0 requires postgresql://
    _db_url = os.environ.get('DATABASE_URL', f'sqlite:///{os.path.join(BASE_DIR, "art_erp.db")}')
    if _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024
    PERMANENT_SESSION_LIFETIME = timedelta(hours=10)
    WTF_CSRF_ENABLED = True
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx'}

    DIAVGEIA_API = 'https://diavgeia.gov.gr/luminapi/api'
    DIAVGEIA_KEYWORDS = ['συντήρηση μνημείων', 'αποκατάσταση', 'συντήρηση έργων τέχνης', 'στερέωση', 'αναστήλωση']
    ESIDIS_SEARCH_URL = 'https://www.eprocurement.gov.gr/kimds2/protected/searchTenders.htm'
    SCHEDULER_ENABLED = os.environ.get('SCHEDULER_ENABLED', 'true').lower() == 'true'
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
    GOOGLE_SERVICE_ACCOUNT_FILE = os.environ.get('GOOGLE_SERVICE_ACCOUNT_FILE', '')
    GOOGLE_DRIVE_ROOT_FOLDER_ID = os.environ.get('GOOGLE_DRIVE_ROOT_FOLDER_ID', '')
    # Email notifications (optional — leave empty to disable)
    MAIL_SERVER   = os.environ.get('MAIL_SERVER', '')
    MAIL_PORT     = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS  = os.environ.get('MAIL_USE_TLS', 'true')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_FROM     = os.environ.get('MAIL_FROM', os.environ.get('MAIL_USERNAME', ''))
    ADMIN_EMAIL   = os.environ.get('ADMIN_EMAIL', '')

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql://erp_user:erp_pass@db:5432/art_erp')

class DevelopmentConfig(Config):
    DEBUG = True
