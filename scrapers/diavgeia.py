"""
ΔΙΑΥΓΕΙΑ REST API scraper
Docs: https://diavgeia.gov.gr/luminapi/api/
"""
import requests
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

BASE_URL = 'https://diavgeia.gov.gr/luminapi/api'

# CPV κωδικοί σχετικοί με συντήρηση/αποκατάσταση
CONSERVATION_CPV = [
    '92521100', '92521200',  # Μουσεία, συλλογές
    '71251000', '71320000',  # Αρχιτεκτονικές υπηρεσίες
    '45212314', '45454100',  # Αποκατάσταση κτιρίων
    '45000000',              # Κατασκευαστικές εργασίες
]

KEYWORDS = [
    'συντήρηση μνημείων',
    'αποκατάσταση μνημείων',
    'συντήρηση έργων τέχνης',
    'στερέωση',
    'αναστήλωση',
    'αρχαιολογικοί χώροι',
    'βυζαντινά μνημεία',
    'νεοκλασικά κτήρια',
    'πολιτιστική κληρονομιά',
    'συντήρηση αρχαιοτήτων',
    'εφορεία αρχαιοτήτων',
    'υπουργείο πολιτισμού',
    'εθνική βιβλιοθήκη',
]

TARGET_ORGS = [
    'ΥΠΟΥΡΓΕΙΟ ΠΟΛΙΤΙΣΜΟΥ',
    'ΕΦΟΡΕΙΑ ΑΡΧΑΙΟΤΗΤΩΝ',
    'ΕΘΝΙΚΗ ΒΙΒΛΙΟΘΗΚΗ',
    'ΜΟΥΣΕΙΟ',
    'ΑΡΧΑΙΟΛΟΓΙΚΟ ΜΟΥΣΕΙΟ',
]


def search_tenders(keyword: str, size: int = 20, from_date: date = None) -> list[dict]:
    """Αναζήτηση διαγωνισμών στη ΔΙΑΥΓΕΙΑ."""
    if from_date is None:
        from_date = date.today() - timedelta(days=60)

    params = {
        'q': keyword,
        'type': 'PERIΛΗΨΗ_ΔΙΑΚΗΡΥΞΗΣ,ΠΡΟΚΗΡΥΞΗ_ΔΙΑΓΩΝΙΣΜΟΥ',
        'size': size,
        'sort': 'recent',
        'from_date': from_date.strftime('%Y-%m-%d'),
        'status': 'ΑΝΑΡΤΗΘΗΚΕ',
    }

    try:
        resp = requests.get(f'{BASE_URL}/search', params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get('decisions', []):
            results.append({
                'ada': item.get('ada', ''),
                'title': item.get('subject', ''),
                'authority': item.get('organizationId', ''),
                'url': f"https://diavgeia.gov.gr/decision/view/{item.get('ada', '')}",
                'publication_date': item.get('submissionTimestamp', '')[:10] if item.get('submissionTimestamp') else '',
                'source': 'ΔΙΑΥΓΕΙΑ',
                'description': item.get('extraFieldValues', {}).get('budgetAmount', ''),
            })
        return results
    except Exception as e:
        logger.error(f'ΔΙΑΥΓΕΙΑ search error for "{keyword}": {e}')
        return []


def fetch_all_new_tenders() -> list[dict]:
    """Τρέχει όλα τα keywords και επιστρέφει μοναδικά αποτελέσματα."""
    seen_adas = set()
    all_results = []
    for kw in KEYWORDS:
        for item in search_tenders(kw):
            if item['ada'] not in seen_adas:
                seen_adas.add(item['ada'])
                all_results.append(item)
    logger.info(f'ΔΙΑΥΓΕΙΑ: βρέθηκαν {len(all_results)} νέοι διαγωνισμοί')
    return all_results


def get_decision_details(ada: str) -> dict:
    """Λήψη λεπτομερειών για συγκεκριμένη απόφαση."""
    try:
        resp = requests.get(f'{BASE_URL}/decision/{ada}', timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f'ΔΙΑΥΓΕΙΑ detail error for ADA {ada}: {e}')
        return {}
