# Sprachassistent für Handwerker

Ein FastAPI-basiertes Backend, das Sprache in strukturierte Rechnungsdaten umwandelt.

## Start
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

POST `/process-audio/` mit `multipart/form-data` (`file`) → JSON-Ausgabe