#!/usr/bin/env bash
set -e

echo "=== ART ERP — Τοπική Εγκατάσταση ==="

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "ERROR: Δεν βρέθηκε python3. Εγκαταστήστε Python 3.9+."
  exit 1
fi

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
  echo "→ Δημιουργία virtual environment..."
  python3 -m venv venv
fi

# Activate
source venv/bin/activate

echo "→ Εγκατάσταση βιβλιοθηκών..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# Create upload directories
echo "→ Δημιουργία φακέλων uploads..."
mkdir -p static/uploads/invoices \
         static/uploads/documents \
         static/uploads/cvs \
         static/uploads/employees \
         static/uploads/legal

# Copy .env if not exists
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "→ Δημιουργήθηκε αρχείο .env — αλλάξτε το SECRET_KEY!"
fi

echo ""
echo "=== Εγκατάσταση ολοκληρώθηκε! ==="
echo ""
echo "Για να εκκινήσετε την εφαρμογή:"
echo "  source venv/bin/activate"
echo "  python app.py"
echo ""
echo "Ανοίξτε το browser στη διεύθυνση: http://127.0.0.1:5000"
echo "Στοιχεία εισόδου: admin / ArtRestore2026!"
