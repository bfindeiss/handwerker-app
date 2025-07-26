FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Render.com setzt die Portnummer über die Umgebungsvariable $PORT.
# Per "sh -c" können wir die Variable auswerten und sonst auf 8000 zurückfallen.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]