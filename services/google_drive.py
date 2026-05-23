"""
Google Drive integration — uploads files to organized folders.

Setup:
1. Go to https://console.cloud.google.com/
2. Create a project → Enable Drive API
3. Create a Service Account → Download JSON key
4. Share your Drive folder with the service account email
5. Set GOOGLE_SERVICE_ACCOUNT_FILE=/path/to/key.json in .env
6. Set GOOGLE_DRIVE_ROOT_FOLDER_ID=<folder-id> in .env
"""
import os
import logging

logger = logging.getLogger(__name__)

# Folder structure inside Google Drive root:
DRIVE_FOLDERS = {
    'invoices':       'Τιμολόγια',
    'legal':          'Νομικά Έγγραφα',
    'tenders':        'Διαγωνισμοί',
    'reports':        'Ημερήσιες Αναφορές',
    'certifications': 'Πιστοποιήσεις Υπαλλήλων',
    'documents':      'Έγγραφα Έργων',
}


def _get_service(app=None):
    """Build and return an authenticated Drive API service, or None if not configured."""
    try:
        from googleapiclient.discovery import build
        from google.oauth2 import service_account

        from flask import current_app
        ctx = app or current_app._get_current_object()
        creds_file = ctx.config.get('GOOGLE_SERVICE_ACCOUNT_FILE', '')
        if not creds_file or not os.path.exists(creds_file):
            return None

        creds = service_account.Credentials.from_service_account_file(
            creds_file,
            scopes=['https://www.googleapis.com/auth/drive.file']
        )
        return build('drive', 'v3', credentials=creds, cache_discovery=False)
    except Exception as e:
        logger.warning(f'Google Drive service unavailable: {e}')
        return None


def _get_or_create_folder(service, folder_name: str, parent_id: str) -> str:
    """Return the Drive folder ID, creating it if it doesn't exist."""
    query = (f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'"
             f" and '{parent_id}' in parents and trashed=false")
    results = service.files().list(q=query, fields='files(id)').execute()
    items = results.get('files', [])
    if items:
        return items[0]['id']
    meta = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id],
    }
    folder = service.files().create(body=meta, fields='id').execute()
    return folder['id']


def upload_file(local_path: str, category: str, subfolder: str = '', filename: str = '') -> str | None:
    """
    Upload a local file to Google Drive in the correct folder.

    Args:
        local_path: Absolute path to the local file.
        category: One of DRIVE_FOLDERS keys (e.g. 'invoices', 'legal').
        subfolder: Optional sub-folder name (e.g. year '2026' or project code).
        filename: Drive filename (defaults to basename of local_path).

    Returns:
        Drive file ID on success, None if Drive is not configured or on error.
    """
    try:
        from flask import current_app
        service = _get_service()
        if not service:
            return None

        root_id = current_app.config.get('GOOGLE_DRIVE_ROOT_FOLDER_ID', '')
        if not root_id:
            return None

        # Navigate to category folder
        cat_name = DRIVE_FOLDERS.get(category, category)
        cat_id = _get_or_create_folder(service, cat_name, root_id)

        # Optional sub-folder (e.g. year or project)
        parent_id = cat_id
        if subfolder:
            parent_id = _get_or_create_folder(service, subfolder, cat_id)

        # Upload file
        from googleapiclient.http import MediaFileUpload
        import mimetypes
        mime, _ = mimetypes.guess_type(local_path)
        mime = mime or 'application/octet-stream'

        drive_name = filename or os.path.basename(local_path)
        file_meta = {'name': drive_name, 'parents': [parent_id]}
        media = MediaFileUpload(local_path, mimetype=mime, resumable=True)
        uploaded = service.files().create(body=file_meta, media_body=media, fields='id').execute()
        file_id = uploaded.get('id')
        logger.info(f'Uploaded {drive_name} to Drive [{category}/{subfolder}] → {file_id}')
        return file_id

    except Exception as e:
        logger.error(f'Drive upload failed: {e}')
        return None


def is_configured() -> bool:
    """Return True if Google Drive credentials are available."""
    try:
        from flask import current_app
        creds = current_app.config.get('GOOGLE_SERVICE_ACCOUNT_FILE', '')
        root  = current_app.config.get('GOOGLE_DRIVE_ROOT_FOLDER_ID', '')
        return bool(creds and root and os.path.exists(creds))
    except Exception:
        return False
