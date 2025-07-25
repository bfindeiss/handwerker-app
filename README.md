# Sprachassistent für Handwerker

Ein FastAPI-basiertes Backend, das Sprache in strukturierte Rechnungsdaten umwandelt und diese an ein Rechnungssystem weiterreicht.

## Start
Uvicorn ist ein schlanker ASGI-Server, mit dem die FastAPI-Anwendung gestartet
wird. Es wird automatisch über die `requirements.txt` mitinstalliert.
```bash
pip install -r requirements.txt
# installiert auch uvicorn, den ASGI-Server für FastAPI
# alternativ: pip install uvicorn
cp .env.example .env  # OPENAI_API_KEY setzen
uvicorn app.main:app --reload
```

POST `/process-audio/` mit `multipart/form-data` (`file`) gibt das erkannte Transkript sowie die extrahierte Rechnung als JSON zurück. Alle Daten werden zur Nachvollziehbarkeit im Ordner `data/` abgelegt.

## Tests ausführen
```bash
pytest
```

