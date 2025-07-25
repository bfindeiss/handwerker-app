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
# optional: BILLING_ADAPTER=app.billing_adapters.simple:SimpleAdapter
# bei Anbindung an sevDesk per MCP:
# BILLING_ADAPTER=app.billing_adapters.sevdesk_mcp:SevDeskMCPAdapter
# MCP_ENDPOINT=http://localhost:8001
# LLM_PROVIDER=openai|ollama
# LLM_MODEL=gpt-4o
# STT_PROVIDER=openai|command
# STT_MODEL=whisper-1
# TELEPHONY_PROVIDER=twilio|sipgate
uvicorn app.main:app --reload
```

## Telefonie konfigurieren

Je nach Anbieter wird ein anderer Webhook aktiviert. In der `.env` kann mit
`TELEPHONY_PROVIDER` entweder `twilio` oder `sipgate` gewählt werden.

| Provider | Voice-Webhook                | Recording-Webhook             |
| -------- | --------------------------- | ----------------------------- |
| Twilio   | `/twilio/voice`             | `/twilio/recording`           |
| sipgate  | `/sipgate/voice`            | `/sipgate/recording`          |

Die eigene Rufnummer muss beim jeweiligen Anbieter so eingerichtet werden,
dass eingehende Anrufe auf den entsprechenden `voice`-Endpunkt verweisen.
Nach dem Auflegen ruft der Provider den zugehörigen `recording`-Endpunkt auf,
woraufhin die Audiodaten gespeichert und verarbeitet werden.

Ist der Server gestartet, kann Audio per HTTP-POST an die Anwendung
gesendet werden. Das folgende Beispiel verwendet `curl` und schickt
eine WAV-Datei an den Endpunkt:

```bash
curl -X POST -F "file=@/pfad/zu/audio.wav" \
  http://127.0.0.1:8000/process-audio/
```

Der zu nutzende Rechnungsadapter kann über die Umgebungsvariable
`BILLING_ADAPTER` angegeben werden. Standardmäßig wird ein Dummy-Adapter
verwendet, der die Rechnung nur speichert.
Möchtest du Rechnungen direkt an sevDesk übermitteln, kannst du den
`SevDeskMCPAdapter` nutzen, der das Model Context Protocol spricht.

Die Antwort enthält das erkannte Transkript, die extrahierten
Rechnungsdaten sowie Informationen zum Speicherort der Ablage im
Verzeichnis `data/`.

POST `/process-audio/` mit `multipart/form-data` (`file`) gibt das erkannte Transkript sowie die extrahierte Rechnung als JSON zurück. Alle Daten werden zur Nachvollziehbarkeit im Ordner `data/` abgelegt.

## Lokaler LLM (Ollama)
Um ein lokales Modell über Ollama zu nutzen, muss zunächst der Ollama Server laufen:
```bash
ollama serve &
```
Dann in der `.env` folgende Einstellungen setzen:
```bash
LLM_PROVIDER=ollama
LLM_MODEL=mistral
```
`OLLAMA_BASE_URL` kann bei Bedarf angepasst werden. Danach wie gewohnt `uvicorn` starten und Anfragen an `/process-audio/` senden.

## Tests ausführen
```bash
pytest
```

