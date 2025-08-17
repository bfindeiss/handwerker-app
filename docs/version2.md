# Version 2 Roadmap

Dieses Dokument dient als Fortschrittskontrolle für die Weiterentwicklung der
Handwerker-App. Es basiert auf dem aktuellen Stand (Version 1) und beschreibt
geplante Erweiterungen für Version 2.

## Features für lokale Nutzung

| Feature | Status | Notizen |
| --- | --- | --- |
| WebRTC/gRPC-Audiostreaming | TODO | Aktuell werden Dateien hochgeladen. |
| EN 16931 / XRechnung-Export | **Implementiert** | Einfache XML-Ausgabe (`app/xrechnung.py`). |
| Erweiterte Preislogik (Material-Lookup, Steuerberechnung) | **Implementiert** | Materialpreise und MwSt. in `app/pricing.py`. |
| Weitere Billing-/CRM-Adapter | TODO | Nur einfache Adapter vorhanden. |
| Weboberfläche zur Rechnungsprüfung | TODO | Noch keine UI. |
| Mobile App/PWA | TODO | Nicht begonnen. |

## Features für Server-Deployment

Diese Punkte werden relevant, sobald die Anwendung auf einem Server betrieben
wird.

| Feature | Status |
| --- | --- |
| Persistente Sitzungen (z. B. Redis) | TODO |
| Skalierbares Streaming mit Lastverteilung | TODO |
| Benutzer- und Mandantenkonzept | TODO |
| Verschlüsselte Speicherung & DSGVO-Löschung | TODO |
| Plugin-Ökosystem für Drittanbieter | TODO |
| Monitoring & Metrics (OpenTelemetry, CI/CD) | TODO |

## Aktueller Stand

- **Implementierte lokale Features:**
  - Grundlegender XRechnung-Export.
  - Materialpreis-Datenbank mit MwSt.-Berechnung.
- **Ausstehende lokale Features:** Streaming, weitere Adapter, Frontend/PWA.
- **Server-Deployment Features:** alle noch offen.

Dieses Dokument kann bei jeder Iteration aktualisiert werden, um den Fortschritt
hin zu Version 2 zu verfolgen.
