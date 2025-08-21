# Anforderungsdokument – "Sprachassistent für Handwerker"

## 1 Einleitung

### 1.1 Zweck
Dieses Dokument beschreibt die Anforderungen an die Anwendung "Sprachassistent für Handwerker". Grundlage sind der vorhandene Quellcode, die Dokumentation und gängige Normen des Requirements Engineering (u. a. ISO/IEC/IEEE 29148:2018). Ziel ist die eindeutige Definition der gewünschten Funktionen und Rahmenbedingungen für Entwicklung, Betrieb und Wartung.

### 1.2 Produktumfang
Das System verarbeitet Sprachaufnahmen und erzeugt strukturierte E‑Rechnungen nach EN 16931 (z. B. XRechnung, ZUGFeRD). Die Rechnungsdaten können an ein externes Fakturierungssystem übergeben und lokal archiviert werden.

### 1.3 Definitionen, Akronyme, Abkürzungen
- **API** – Application Programming Interface
- **EN 16931** – Europäische Norm für elektronische Rechnungen
- **LLM** – Large Language Model
- **STT** – Speech-to-Text
- **TTS** – Text-to-Speech

### 1.4 Referenzen
- ISO/IEC/IEEE 29148:2018 – Systems and software engineering — Life cycle processes — Requirements engineering
- EN 16931 — Electronic invoicing
- Datenschutz-Grundverordnung (DSGVO)

### 1.5 Überblick
Kapitel 2 beschreibt das Produktkonzept, Kapitel 3 die funktionalen Anforderungen, Kapitel 4 die Schnittstellen, Kapitel 5 nicht-funktionale Anforderungen und Kapitel 6 Datenanforderungen. Kapitel 7 fasst Qualitätsmaßnahmen zusammen.

---

## 2 Produktübersicht

### 2.1 Produktperspektive
Das System ist ein serverseitiges Python-Backend (FastAPI) und bietet einen Web- sowie Telefonieservice für die Rechnungserstellung. Hauptprozesse: Audioupload, Transkription, Extraktion von Rechnungsdaten durch ein LLM, Preiskalkulation, Übergabe an ein Rechnungssystem und Persistenz aller Artefakte.

### 2.2 Produktfunktionen
- Upload von Audioaufnahmen und automatische Konvertierung in WAV
- Auswahl eines STT-Providers (OpenAI, lokales Kommandozeilen-Tool, Whisper) und Transkriptnormierung
- Extraktion eines strukturierten Rechnungskontexts via LLM (OpenAI oder Ollama)
- Ergänzung fehlender Preise, Netto- und Steuerberechnung, Rechnungsnummer und Datum
- Pluggable Billing-Adapter zur Übergabe an externe Systeme oder Dummy-Verarbeitung
- Speicherung aller Sitzungsdaten (Audio, Transkript, JSON, PDF, XML) im Dateisystem
- Telefonieschnittstellen für Twilio und Sipgate, inklusive Rückfragen bei unvollständigen Daten
- Interaktive Korrekturen und Fortschreibung des Rechnungszustands über Konversationsendpunkte
- Text-zu-Sprache-Ausgabe für akustische Rückmeldungen an den Nutzer

### 2.3 Benutzercharakteristika
- **Handwerker**: Erstellen Rechnungen per Sprache über Weboberfläche oder Telefon.
- **Systemadministratoren**: Konfigurieren Provider, Umgebungsvariablen und Deployment.
- **Rechnungssystembetreiber**: Empfangen die erzeugten Rechnungsdaten.

### 2.4 Randbedingungen
- Python-Laufzeit mit FastAPI; FFMPEG und ggf. NumPy für lokale STT.
- Externe Dienste (OpenAI, Ollama, Twilio/Sipgate, Billing-Systeme) erfordern gültige Zugangsdaten.
- Speicherung erfolgt lokal im Verzeichnis `data/`; ausreichender Speicherplatz ist sicherzustellen.

### 2.5 Annahmen und Abhängigkeiten
- Nutzer verfügen über geeignete Audioeingabegeräte.
- Internetverbindung vorhanden, sofern Cloud-Provider verwendet werden.
- Rechnungsrelevante Unternehmensdaten stehen als Umgebungsvariablen zur Verfügung.

---

## 3 Systemfunktionen (funktionale Anforderungen)

| Nr. | Bezeichnung | Beschreibung |
|-----|-------------|--------------|
| **FR1** | Audioupload | Das System muss Audiodateien entgegennehmen, ggf. in WAV konvertieren und die weitere Verarbeitung einleiten. |
| **FR2** | Transkription | Es muss konfigurierbare STT-Provider unterstützen und das Transkript normalisieren (Zahlwörter, definierte Ersetzungen). |
| **FR3** | LLM-Extraktion | Aus dem Transkript ist ein JSON-Rechnungsmodell zu generieren; das System muss mindestens OpenAI und Ollama unterstützen. |
| **FR4** | Preisermittlung | Für Positionen ohne Preis sind Standardpreise oder Materialpreise zu ergänzen; Gesamt-, Netto- und Steuerbeträge sind zu berechnen. |
| **FR5** | Rechnungssystem-Anbindung | Über ein Adapter-Konzept sollen Rechnungen an externe Systeme übermittelt oder lokal verarbeitet werden können. |
| **FR6** | Persistenz | Jede Sitzung ist mit Audio, Transkript, JSON, PDF und XRechnung-XML im Dateisystem abzulegen. |
| **FR7** | Telefondialog | Für Telefonanrufer muss das System Gesprächsaufzeichnungen entgegennehmen, transkribieren und bei fehlenden Daten Rückfragen stellen. |
| **FR8** | Weboberfläche | Eine HTML-Oberfläche ist bereitzustellen, über die Audio aufgezeichnet und hochgeladen werden kann. |
| **FR9** | Interaktive Korrekturen | Während einer Sitzung sollen Benutzer Rechnungsdaten ergänzen oder überschreiben können; das System führt Teiltranskripte zusammen und aktualisiert den Rechnungszustand. |
| **FR10** | Akustische Ausgabe | Das System muss Text in Sprache umwandeln und als Audio (z. B. Base64) zurückliefern können. |
| **FR11** | Backend-Verfügbarkeit | Beim Start ist die Erreichbarkeit des LLM-Backends zu prüfen; optional soll der Start bei Nichtverfügbarkeit abbrechen. |

---

## 4 Externe Schnittstellenanforderungen

### 4.1 Benutzeroberflächen
- **Webinterface**: Endpoint `/web` liefert eine HTML-Seite für Aufnahme und Upload von Audio.
- **Telefonie**: Webhooks `/twilio/voice`, `/twilio/recording` bzw. `/sipgate/...` ermöglichen sprachgesteuerte Interaktionen über Telefonnetz.

### 4.2 Software-Schnittstellen
- **REST-API**: `/process-audio/` nimmt `multipart/form-data` mit Feld `file` entgegen und liefert JSON mit Transkript, Rechnungsdaten, Ergebnis der Rechnungserstellung und Pfaden zu Artefakten zurück.
- **STT-Provider**: Konfiguration über `STT_PROVIDER` (`openai`, `command`, `whisper`); Schnittstellen gemäß jeweiligen SDKs bzw. CLI.
- **LLM-Provider**: `LLM_PROVIDER` (`openai`, `ollama`); Prompt-Format festgelegt in `_build_prompt`.
- **Billing-Adapter**: Dynamisches Laden via `module:Class`, erweiterbar für unterschiedliche Systeme.
- **TTS-Provider**: `TTS_PROVIDER` (`gtts`, `elevenlabs`).

### 4.3 Datenpersistenz
Artefakte liegen im Verzeichnis `data/<ISO-Timestamp>/`; darunter jeweils `audio.wav`, `transcript.json`, `transcript.txt`, `invoice.json`, `invoice.pdf`, `invoice.xml`.

### 4.4 Kommunikationsschnittstellen
HTTP(S) für Web und APIs; Telefondienste via HTTPS-Webhooks. Externe Dienste (OpenAI, Ollama, Twilio, Sipgate, ElevenLabs) erfordern Internetzugang und Authentifizierung.

---

## 5 Nicht-funktionale Anforderungen

### 5.1 Leistung
- Transkription und LLM-Aufruf sollen innerhalb akzeptabler Zeit erfolgen; Laufzeiten werden geloggt.
- Gleichzeitige Sessions müssen verarbeitet werden können; Skalierung über FastAPI/ASGI.

### 5.2 Zuverlässigkeit
- Jeder Request erhält eine eindeutige `X-Request-ID` zur Nachvollziehbarkeit und Fehlerdiagnose.
- Fehlende Pflichtfelder lösen gezielte Rückfragen oder Fehlercodes aus.

### 5.3 Sicherheit und Datenschutz
- Personenbezogene Daten in LLM-Prompts werden maskiert, bevor sie geloggt werden (Funktion `mask_pii`, nicht dargestellt).
- Daten werden lokal gespeichert; Betreiber sind für DSGVO-konforme Aufbewahrung und Löschung verantwortlich.
- Unsichere Zeichen in extern konfigurierten Kommandos werden geprüft, um Kommandoinjektion zu verhindern.

### 5.4 Benutzbarkeit
- Sprachdialog führt den Nutzer durch fehlende Angaben.
- Webinterface ist ohne zusätzliche Software nutzbar.

### 5.5 Wartbarkeit
- Modulares Design mit klar abgegrenzten Komponenten (STT, LLM, Billing, Telephony) erleichtert Erweiterungen.
- Umgebungsvariablen ermöglichen flexible Konfiguration ohne Codeänderung.

### 5.6 Portierbarkeit
- Deployment über Docker, Render oder AWS Lambda möglich (siehe README).
- Unterstützt lokale und Cloud-basierte KI-Modelle; Austausch von Providern durch Adapter.

### 5.7 Gesetzliche und regulatorische Anforderungen
- Rechnungen orientieren sich an EN 16931.
- Bei Verarbeitung personenbezogener Daten sind DSGVO-Vorgaben einzuhalten.

---

## 6 Datenanforderungen

### 6.1 Datenmodelle
- `InvoiceItem`: Beschreibung, Kategorie (`material|travel|labor`), Menge, Einheit, Preis und optional Rolle des Mitarbeiters. Enthält berechnetes `total`.
- `InvoiceContext`: Gesamte Rechnung mit Kunde, Dienstleistung, Positionen, Beträgen, Rechnungsnummer und Datum.
- Parser entfernt ungültige JSON-Fragmente, ordnet Kategorien zu und normalisiert Einheiten.

### 6.2 Persistente Daten
- Sämtliche Interaktionen werden als Audit-Trail im Dateisystem abgelegt (s. Kap. 4.3).
- Materialpreislisten und Service-Templates können aus YAML/JSON geladen und angepasst werden.

---

## 7 Qualitätssicherung

- **Tests**: `pytest`-Suite deckt Kernfunktionen ab; CI-Workflows liefern Coverage-Berichte.
- **Logging**: Strukturierte Logausgaben mit Zeitstempeln und Request-IDs.
- **Konfigurationsprüfung**: Beim Start wird die Erreichbarkeit des LLM-Backends verifiziert, damit Betriebsfehler früh erkannt werden.

---

## 8 Anhang

### 8.1 Offene Punkte
- EN 16931-Konformität der erzeugten PDF/XML-Rechnungen ist derzeit nur teilweise umgesetzt und muss bei Bedarf erweitert werden.
- Sicherheitsaspekte wie Authentifizierung/Autorisierung der Web- und Telefonieschnittstellen sind nach Projektbedarf zu ergänzen.

---

*Dieses Dokument folgt den Empfehlungen der ISO/IEC/IEEE 29148 und bildet die Grundlage für weitere Spezifikation, Implementierung und Validierung des "Sprachassistenten für Handwerker".*

