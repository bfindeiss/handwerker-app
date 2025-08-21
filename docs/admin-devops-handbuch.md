# Admin- und DevOps-Handbuch

Dieses Handbuch unterstützt Administratoren und DevOps-Teams beim Betrieb der Handwerker-App.

## Systemvoraussetzungen
- Docker und Docker Compose
- Zugriff auf das Container-Registry und das Konfigurations-Repository

## Deployment
1. Klonen Sie das Repository.
2. Führen Sie `docker compose up --build` aus.
3. Setzen Sie erforderliche Umgebungsvariablen wie `BILLING_ADAPTER` und `MCP_ENDPOINT`.

## Wartung
- Überwachen Sie Logs und Metriken mittels Prometheus/Loki oder vergleichbaren Tools.
- Spielen Sie regelmäßig Sicherheitsupdates ein.
- Führen Sie Backups der Datenbank durch.

## Skalierung
- Nutzen Sie Container-Orchestrierung wie Kubernetes für horizontale Skalierung.
- Verwenden Sie Load Balancer für hohe Verfügbarkeit.

## Troubleshooting
- Prüfen Sie zuerst die Logs (`docker logs <container>`).
- Validieren Sie Konfigurationen und Netzwerkverbindungen.
