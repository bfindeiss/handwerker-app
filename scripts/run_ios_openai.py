#!/usr/bin/env python3
"""Startet die FastAPI-App in einer iOS-Python-Umgebung (z.B. Pyto).

Das Skript installiert die Abhängigkeiten und kopiert bei Bedarf die
Beispielkonfiguration. Anschließend wird die Anwendung mit Uvicorn
gestartet. Ollama wird nicht unterstützt, daher wird standardmäßig der
OpenAI-Provider genutzt.
"""
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ensure_env_file():
    env_path = os.path.join(REPO_ROOT, ".env")
    example_path = os.path.join(REPO_ROOT, ".env.example")
    if not os.path.exists(env_path):
        with open(example_path, "r") as src, open(env_path, "w") as dst:
            dst.write(src.read())


def main():
    # Pakete installieren
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", os.path.join(REPO_ROOT, "requirements.txt")])
    ensure_env_file()

    # Anwendung starten
    subprocess.call([
        "uvicorn",
        "app.main:app",
        "--reload",
        "--host",
        "0.0.0.0",
    ])


if __name__ == "__main__":
    main()
