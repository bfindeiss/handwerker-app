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

# Lokale Provider verwenden
export LLM_PROVIDER=ollama
export LLM_MODEL=${LLM_MODEL:-deepseek-r1:latest}  # "mistral", "llama3" oder "orca2" funktionieren ebenfalls

# STT_PROVIDER auf "whisper" setzen, falls nicht anders angegeben.
STT_PROVIDER_DEFAULT=${STT_PROVIDER:-whisper}

# Falls "whisper" gewählt ist und NumPy fehlt, zum OpenAI-Provider wechseln.
if [ "$STT_PROVIDER_DEFAULT" = "whisper" ]; then
    if ! python3 - <<'EOF' >/dev/null 2>&1
import importlib.util, sys
sys.exit(0 if importlib.util.find_spec("numpy") else 1)
EOF
    then
        echo "NumPy nicht gefunden, STT_PROVIDER=openai wird verwendet." >&2
        STT_PROVIDER_DEFAULT="openai"
    fi
fi

export STT_PROVIDER=$STT_PROVIDER_DEFAULT
export STT_MODEL=${STT_MODEL:-base}

# Ollama-Server im Hintergrund starten
ollama serve &
OLLAMA_PID=$!

# FastAPI-Anwendung starten
uvicorn app.main:app --reload --host 0.0.0.0

# beim Beenden auch den Ollama-Server stoppen
kill $OLLAMA_PID
