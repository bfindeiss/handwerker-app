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

Ist der Server gestartet, kann Audio per HTTP-POST an die Anwendung
gesendet werden. Das folgende Beispiel verwendet `curl` und schickt
eine WAV-Datei an den Endpunkt:

```bash
curl -X POST -F "file=@/pfad/zu/audio.wav" \
  http://127.0.0.1:8000/process-audio/
```

Die Antwort enthält das erkannte Transkript, die extrahierten
Rechnungsdaten sowie Informationen zum Speicherort der Ablage im
Verzeichnis `data/`.

POST `/process-audio/` mit `multipart/form-data` (`file`) gibt das erkannte Transkript sowie die extrahierte Rechnung als JSON zurück. Alle Daten werden zur Nachvollziehbarkeit im Ordner `data/` abgelegt.

## Tests ausführen
```bash
pytest
```

