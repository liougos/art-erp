FROM python:3.11-slim

WORKDIR /app

# System dependencies for Pillow, psycopg2, pytesseract
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    tesseract-ocr \
    tesseract-ocr-ell \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create upload directories
RUN mkdir -p static/uploads/invoices \
             static/uploads/documents \
             static/uploads/cvs \
             static/uploads/employees \
             static/uploads/legal

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120", "app:create_app()"]
