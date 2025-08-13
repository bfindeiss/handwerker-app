# Sprachassistent für Handwerker

[![codecov](https://codecov.io/gh/OWNER/handwerker-app/branch/main/graph/badge.svg)](https://codecov.io/gh/OWNER/handwerker-app)

Ein FastAPI-basiertes Backend, das Sprache in strukturierte Rechnungsdaten umwandelt und diese an ein Rechnungssystem weiterreicht.
Es erzeugt positionsgenaue E-Rechnungen nach EN 16931 (z. B. XRechnung/ZUGFeRD) mit Material-, Anfahrts- und Arbeitszeitposten
inklusive unterschiedlicher Stundensätze für Gesellen und Meister.

## Inhaltsverzeichnis

- [Installation und Start](#installation-und-start)
- [Telefonie konfigurieren](#telefonie-konfigurieren)
- [Audioverarbeitung & Weboberfläche](#audioverarbeitung--weboberfläche)
- [Lokaler LLM (Ollama)](#lokaler-llm-ollama)
- [MacBook Pro: Lokale Ausführung mit Ollama](#macbook-pro-lokale-ausführung-mit-ollama)
- [Tests ausführen](#tests-ausführen)
- [Code Coverage in GitHub anzeigen](#code-coverage-in-github-anzeigen)
- [Deployment auf Render](#deployment-auf-render)
- [iPhone: Lokaler Test mit Pyto (experimentell)](#iphone-lokaler-test-mit-pyto-experimentell)
- [Fehlerbehebung](#fehlerbehebung)
  - ["WhisperTranscriber requires ffmpeg"](#whispertranscriber-requires-ffmpeg)
  - ["Numpy is not available"](#numpy-is-not-available)
  - ["A module that was compiled using NumPy 1.x cannot be run"](#a-module-that-was-compiled-using-numpy-1x-cannot-be-run)

## Installation und Start

Uvicorn ist ein schlanker ASGI-Server, mit dem die FastAPI-Anwendung gestartet wird. Es wird automatisch über die `requirements.txt` mitinstalliert.

```bash
pip install -r requirements.txt
# installiert auch uvicorn, den ASGI-Server für FastAPI
# alternativ: pip install uvicorn
cp .env.example .env  # bei lokaler Nutzung ist kein OPENAI_API_KEY nötig
# optional: BILLING_ADAPTER=app.billing_adapters.simple:SimpleAdapter
# bei Anbindung an sevDesk per MCP:
# BILLING_ADAPTER=app.billing_adapters.sevdesk_mcp:SevDeskMCPAdapter
# MCP_ENDPOINT=http://localhost:8001
# LLM_PROVIDER=ollama|openai
# LLM_MODEL=deepseek-r1:latest  # alternativ: llama3, orca2, mistral
# STT_PROVIDER=whisper|openai|command
# Für whisper/command muss ffmpeg als System-Binary installiert sein
# z.B. "brew install ffmpeg" (macOS) oder "sudo apt install ffmpeg" (Ubuntu)
# STT_MODEL=base
# TELEPHONY_PROVIDER=twilio|sipgate
# TTS_PROVIDER=gtts|elevenlabs
uvicorn app.main:app --reload
# Weboberfläche anschließend unter http://localhost:8000/web
```

## Telefonie konfigurieren

Je nach Anbieter wird ein anderer Webhook aktiviert. In der `.env` kann mit `TELEPHONY_PROVIDER` entweder `twilio` oder `sipgate` gewählt werden.

| Provider | Voice-Webhook                | Recording-Webhook             |
| -------- | --------------------------- | ----------------------------- |
| Twilio   | `/twilio/voice`             | `/twilio/recording`           |
| sipgate  | `/sipgate/voice`            | `/sipgate/recording`          |

Die eigene Rufnummer muss beim jeweiligen Anbieter so eingerichtet werden, dass eingehende Anrufe auf den entsprechenden `voice`-Endpunkt verweisen. Nach dem Auflegen ruft der Provider den zugehörigen `recording`-Endpunkt auf, woraufhin die Audiodaten gespeichert und verarbeitet werden.

## Audioverarbeitung & Weboberfläche

Ist der Server gestartet, kann Audio per HTTP-POST an die Anwendung gesendet werden. Das folgende Beispiel verwendet `curl` und schickt eine WAV-Datei an den Endpunkt:

```bash
curl -X POST -F "file=@/pfad/zu/audio.wav" \
  http://127.0.0.1:8000/process-audio/
```

Der zu nutzende Rechnungsadapter kann über die Umgebungsvariable `BILLING_ADAPTER` angegeben werden. Standardmäßig wird ein Dummy-Adapter verwendet, der die Rechnung nur speichert. Möchtest du Rechnungen direkt an sevDesk übermitteln, kannst du den `SevDeskMCPAdapter` nutzen, der das Model Context Protocol spricht.

Die Antwort enthält das erkannte Transkript, die extrahierten Rechnungsdaten sowie Informationen zum Speicherort der Ablage im Verzeichnis `data/`. POST `/process-audio/` mit `multipart/form-data` (`file`) gibt das erkannte Transkript sowie die extrahierte Rechnung als JSON zurück. Alle Daten werden zur Nachvollziehbarkeit im Ordner `data/` abgelegt.

### Weboberfläche

Zum schnellen Testen gibt es eine kleine HTML-Oberfläche unter `/web`. Dort kann direkt im Browser eine Aufnahme gestartet und anschließend als WAV-Datei an `/process-audio/` gesendet werden. Das Ergebnis wird nach dem Upload auf der Seite dargestellt.

## Lokaler LLM (Ollama)

Um ein lokales Modell über Ollama zu nutzen, muss zunächst der Ollama Server laufen:

```bash
ollama serve &
```

Dann in der `.env` folgende Einstellungen setzen:

```bash
LLM_PROVIDER=ollama
LLM_MODEL=deepseek-r1:latest
```

Das Modell `deepseek-r1:latest` liefert leistungsfähige Ergebnisse. Kleinere Modelle wie `mistral:latest`, `llama3:latest` oder `orca2:latest` funktionieren ebenfalls und benötigen weniger Ressourcen. `OLLAMA_BASE_URL` kann bei Bedarf angepasst werden. Danach wie gewohnt `uvicorn` starten und Anfragen an `/process-audio/` senden.

## MacBook Pro: Lokale Ausführung mit Ollama

Folgende Schritte richten das Projekt auf macOS ein und starten es. Alle Befehle können durch Ausführen des beiliegenden Skripts `scripts/run_mac_ollama.sh` mit einem Klick ausgeführt werden.

```bash
# Repository klonen und ins Verzeichnis wechseln
# git clone <diese-repo-url> handwerker-app
# cd handwerker-app

# Startskript ausführen
bash scripts/run_mac_ollama.sh
```

Das Skript erstellt ein virtuelles Python-Environment, installiert die Abhängigkeiten, kopiert bei Bedarf die Beispielkonfiguration und startet anschließend den Ollama-Server sowie die FastAPI-Anwendung. Fehlt NumPy, setzt das Skript automatisch `STT_PROVIDER=openai`. Bei Bedarf lassen sich die Befehle auch manuell ausführen:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# NumPy ist erforderlich, wenn STT_PROVIDER=whisper verwendet wird.
# Das Startskript wechselt bei fehlendem NumPy automatisch zu
# STT_PROVIDER=openai.
cp .env.example .env
ollama serve &
export LLM_PROVIDER=ollama
export STT_PROVIDER=whisper
uvicorn app.main:app --reload
```

## Tests ausführen

```bash
pytest
```

## Code Coverage in GitHub anzeigen

Um die Testabdeckung direkt auf GitHub nachvollziehen zu können, nutzt dieses Projekt [Codecov](https://about.codecov.io/). Die bestehende GitHub-Action in `.github/workflows/ci.yml` führt die Tests mit Coverage aus und lädt den Bericht anschließend zu Codecov hoch. Damit das funktioniert, sind einige Schritte nötig:

1. Bei Codecov mit dem GitHub-Account anmelden und das Repository `handwerker-app` hinzufügen.
2. In den Repository-Einstellungen bei Codecov den **Upload Token** kopieren.
3. Im GitHub-Repository unter **Settings → Secrets and variables → Actions** einen neuen Secret namens `CODECOV_TOKEN` anlegen und den kopierten Token einfügen.
4. Änderungen committen und pushen. Der CI-Workflow erstellt dabei automatisch die Datei `coverage.xml` (siehe `pytest.ini`) und lädt sie zu Codecov hoch.
5. Nach erfolgreichem Upload zeigt Codecov in Pull Requests einen Statuscheck bzw. Kommentar an, und das Badge im README wird aktualisiert. Ersetze dafür in der Badge-URL den Platzhalter `OWNER` durch deinen GitHub-Benutzernamen oder die Organisation.

Über das Codecov-Dashboard lassen sich bei Bedarf weitere Einstellungen wie Mindestabdeckung oder PR-Kommentare konfigurieren.

## Deployment auf Render

Für eine kostengünstige Bereitstellung bietet [Render](https://render.com) einen kostenlosen Tarif, der für kleinere Projekte ausreicht. Die Anwendung lässt sich dank Dockerfile einfach deployen:

1. Bei Render registrieren und das Repository verknüpfen.
2. Beim Erstellen eines neuen **Web Service** die Option "Docker" wählen. Render erkennt die Datei `render.yaml` automatisch.
3. Die in `.env.example` aufgeführten Variablen im Dashboard anlegen.
4. Nach dem Deploy lauscht die App auf dem von Render vorgegebenen Port (`$PORT`). Der Dockerfile wurde entsprechend angepasst.

Damit läuft der Sprachassistent günstig in der Cloud und kann über die öffentliche URL von Render erreicht werden.

## iPhone: Lokaler Test mit Pyto (experimentell)

Um die Anwendung direkt auf einem iPhone zu starten, kann die App [Pyto](https://apps.apple.com/app/pyto-python-3/id1436650069) verwendet werden. Nach dem Kopieren des Repository-Verzeichnisses (z.B. via iCloud) öffnest du in Pyto das Skript `scripts/run_ios_openai.py` und führst es aus. Das Skript installiert die Python-Abhängigkeiten, legt falls nötig eine `.env`-Datei an und startet anschließend `uvicorn`.

Aufgrund fehlender Ollama-Unterstützung nutzt diese Variante den OpenAI-Provider. Achte darauf, deinen `OPENAI_API_KEY` in der `.env` zu hinterlegen. Danach ist die Weboberfläche unter `http://localhost:8000/web` erreichbar und es lassen sich wie gewohnt Audioaufnahmen hochladen.

## Fehlerbehebung

### "WhisperTranscriber requires ffmpeg"

Beim lokalen Whisper-Modell (`STT_PROVIDER=whisper`) muss das Programm `ffmpeg` installiert und im `PATH` verfügbar sein. Installiere es bei Bedarf über `brew install ffmpeg` (macOS) oder `sudo apt install ffmpeg` (Ubuntu). Alternativ kann `STT_PROVIDER=openai` gesetzt werden, um den Cloud-Dienst ohne lokales `ffmpeg` zu nutzen.

### "Numpy is not available"

Beim Einsatz des lokalen Whisper-Modells (`STT_PROVIDER=whisper`) muss `numpy` installiert sein. Erscheint beim Start die Meldung `RuntimeError: Numpy is not available`, fehlt das Paket in der aktuellen Umgebung. Installiere es nachträglich mit:

```bash
pip install numpy
```

Alternativ kann `STT_PROVIDER=openai` gesetzt werden, um das Whisper-Modell von OpenAI zu verwenden, das ohne lokales `numpy` auskommt. Wird das Startskript verwendet und NumPy fehlt, erfolgt dieser Wechsel inzwischen automatisch.

### "A module that was compiled using NumPy 1.x cannot be run"

Diese Warnung deutet auf eine inkompatible Kombination von Paketen hin. Ein Modul wurde mit einer NumPy-1.x-Version erstellt, in der aktuellen Umgebung ist jedoch NumPy 2 installiert. Aktualisiere das betroffene Paket oder setze NumPy auf eine 1.x-Version zurück:

```bash
pip install "numpy<2"
```

