"""
ΕΣΗΔΗΣ / ΚΗΜΔΗΣ scraper
Αναζήτηση δημοσίων διαγωνισμών για συντήρηση/αποκατάσταση
"""
import requests
import logging
from bs4 import BeautifulSoup
from datetime import date, timedelta

logger = logging.getLogger(__name__)

ESIDIS_BASE = 'https://www.eprocurement.gov.gr'

KEYWORDS = [
    'συντήρηση μνημείων',
    'αποκατάσταση μνημείων',
    'συντήρηση έργων τέχνης',
    'στερέωση μνημείου',
    'αναστήλωση',
    'πολιτιστική κληρονομιά',
    'αρχαιολογικός χώρος',
    'βυζαντινά μνημεία',
    'συντήρηση αρχαιοτήτων',
]

TARGET_AUTHORITIES = [
    'Υπουργείο Πολιτισμού',
    'Εφορεία Αρχαιοτήτων',
    'Εθνική Βιβλιοθήκη',
    'Μουσείο',
    'Δήμος',
    'Περιφέρεια',
    'Κεντρικό Αρχαιολογικό Συμβούλιο',
]

CPV_CODES = ['92521100', '92521200', '71251000', '45212314', '45454100', '92522100', '92522200']

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'el-GR,el;q=0.9,en;q=0.8',
}


def search_esidis(keyword: str) -> list[dict]:
    """Αναζήτηση στο ΕΣΗΔΗΣ (web scraping)."""
    results = []
    try:
        search_url = f'{ESIDIS_BASE}/kimds2/protected/searchTenders.htm'
        params = {'searchText': keyword, 'searchType': '0'}
        resp = requests.get(search_url, params=params, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        rows = soup.select('table.resultsTable tr[class]')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 4:
                results.append({
                    'title': cols[0].get_text(strip=True),
                    'authority': cols[1].get_text(strip=True),
                    'deadline': cols[2].get_text(strip=True),
                    'budget': cols[3].get_text(strip=True),
                    'source': 'ΕΣΗΔΗΣ',
                    'url': ESIDIS_BASE + (cols[0].find('a', href=True) or {}).get('href', ''),
                })
    except Exception as e:
        logger.warning(f'ΕΣΗΔΗΣ search failed for "{keyword}": {e}')
    return results


def fetch_all_new_tenders() -> list[dict]:
    """Συλλέγει από ΕΣΗΔΗΣ για όλα τα keywords."""
    seen = set()
    results = []
    for kw in KEYWORDS:
        for item in search_esidis(kw):
            key = item.get('title', '')[:80]
            if key not in seen:
                seen.add(key)
                results.append(item)
    logger.info(f'ΕΣΗΔΗΣ: βρέθηκαν {len(results)} αποτελέσματα')
    return results
