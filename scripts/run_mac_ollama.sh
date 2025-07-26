#!/bin/bash
# Schnellstart-Skript für macOS, startet Ollama und die App
set -e

# virtuelles Environment anlegen, falls nicht vorhanden
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

pip install -r requirements.txt

# Beispielkonfiguration kopieren, falls .env fehlt
if [ ! -f .env ]; then
    cp .env.example .env
fi

# Ollama-Server im Hintergrund starten
ollama serve &
OLLAMA_PID=$!

# FastAPI-Anwendung starten
uvicorn app.main:app --reload

# beim Beenden auch den Ollama-Server stoppen
kill $OLLAMA_PID
