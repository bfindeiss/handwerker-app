# Codebase-Dokumentation (sehr ausführlich)

Diese Dokumentation richtet sich an Entwickler:innen, die sich schnell und
verlässlich in der Handwerker‑App zurechtfinden müssen, auch wenn sie den Code
noch nicht im Detail kennen. Sie erklärt Architektur, Datenflüsse, zentrale
Module, Konfiguration und Erweiterungspunkte anhand der tatsächlichen
Implementierung im Repository.

## 1) Überblick und Zielsetzung

**Ziel der Anwendung**: Sprachaufnahmen (oder Bilder via OCR) werden in
strukturierte Rechnungsdaten umgewandelt. Daraus erzeugt das System
E‑Rechnungen (PDF + XML) und kann diese an ein externes Rechnungssystem
weiterleiten.

**Technologie‑Stack**:

- **FastAPI** als Webframework und API‑Layer (`app/main.py`)
- **LLM‑Anbindung** via OpenAI oder Ollama (`app/llm_agent.py`)
- **Speech‑to‑Text (STT)** via OpenAI, lokalem Whisper oder Command‑Backend
  (`app/stt/`)
- **OCR** via Tesseract (`app/ocr.py`)
- **PDF‑ und XML‑Erzeugung** (`app/pdf.py`, `app/xrechnung.py`)
- **Telephony‑Provider** für Twilio/Sipgate (`app/telephony/`)

Die Verarbeitung ist bewusst modular: STT, LLM, TTS, Billing‑Adapter usw. sind
abstrakt gekapselt und können per Konfiguration ausgetauscht werden.

---

## 2) Grobe Architektur (Datenfluss)

**Kernfluss (Audio → Rechnung)**

1. **Upload** einer Audiodatei (HTTP `POST /process-audio/`)
2. **Konvertierung** in WAV (falls nötig)
3. **STT**: Audio → Text (`app/stt.transcribe_audio`)
4. **LLM‑Extraktion**: Text → JSON‑Rechnung (`app/llm_agent.extract_invoice_context`)
5. **Validierung**: JSON → `InvoiceContext` (`app/models.parse_invoice_context`)
6. **Preislogik** + Summen (`app/pricing.apply_pricing`)
7. **Billing‑Adapter** sendet Rechnung (`app/billing_adapter.send_to_billing_system`)
8. **Persistierung** der Artefakte (`app/persistence.store_interaction`)
9. **Antwort** enthält Transkript, Rechnung, PDF‑Pfad, etc.

**Dialog‑Fluss (Conversation)** erweitert Schritt 4‑6 um mehrstufige
Rückfragen und Bestätigungslogik.

**Telephony‑Fluss** hat einen ähnlichen Ablauf wie der Audio‑Upload, wird aber
über Webhooks gesteuert (`/twilio/*`, `/sipgate/*`).

---

## 3) Endpunkte und ihre Logik

### 3.1 `app/main.py`

**Zentrale FastAPI‑App**: `app = FastAPI()`

**Endpoints**:

- `GET /` → Health‑Info
- `GET /web` → Liefert die Web‑UI (HTML aus `app/static/eunoia.html`)
- `POST /process-audio/` → Audio‑Verarbeitung
- `POST /process-image/` → OCR‑Verarbeitung

**Besonderheiten**:

- `@app.middleware("http")`: Jeder Request bekommt eine `X-Request-ID`
  (`app/request_id.py`) für besseres Logging und Debugging.
- `@app.on_event("startup")`: Verifiziert LLM‑Erreichbarkeit
  (`app.llm_agent.check_llm_backend`).
- Statische Dateien sind unter `/static` verfügbar, Sitzungsartefakte unter
  `/data` (`app/main.py`).

### 3.2 `/process-audio/` (Audio‑Upload)

Implementiert in `app/main.py`:

1. Audio in Bytes laden
2. Bei Nicht‑WAV: Konvertierung via ffmpeg (`_convert_to_wav`)
3. STT (`app.stt.transcribe_audio`)
4. LLM‑Extraktion (`app.llm_agent.extract_invoice_context`)
5. Parsing in `InvoiceContext` (`app.models.parse_invoice_context`)
6. Preisberechnung (`app.pricing.apply_pricing`)
7. Billing‑Adapter + Persistierung (`app.billing_adapter`, `app.persistence`)
8. Antwort inkl. `pdf_url` und `log_dir`

### 3.3 `/process-image/` (OCR)

Analog zum Audio‑Flow, aber mit OCR als Eingang (`app/ocr.extract_text`).

### 3.4 `/conversation/` und `/conversation-text/`

Implementiert in `app/conversation.py`.

Der Dialog‑Workflow baut ein konversationelles Sitzungsmodell:

- `SESSIONS`: gesamte Chat‑Historie (User + Assistant)
- `INVOICE_STATE`: letzter konsistenter Rechnungszustand
- `SESSION_STATUS`: z. B. „collecting“, „summarizing“, „awaiting_confirmation“
- `PENDING_CONFIRMATION`: finaler Entwurf vor Bestätigung

Erst wenn Pflichtfelder vollständig sind, wird eine Zusammenfassung erzeugt
(`app.summaries.build_invoice_summary`). Danach wartet die Session auf eine
Bestätigung durch den Nutzer. Korrekturen setzen den Status zurück und
aktualisieren die Rechnung.

### 3.5 Telefonie‑Webhooks

**Twilio** (`app/telephony/twilio.py`):

- `/twilio/voice`: Begrüßung und Start der Aufnahme
- `/twilio/recording`: Verarbeitung und ggf. Rückfragen

**Sipgate** ist analog aufgebaut (`app/telephony/sipgate.py`). Die gemeinsame
Finalisierung passiert in `app/telephony/common.py`:

- `finalize(...)` sendet Rechnung, speichert Artefakte und erzeugt optional eine
  TTS‑MP3.

---

## 4) Datenmodelle und Validierung

### 4.1 Zentrale Modelle (`app/models.py`)

- **`InvoiceContext`**: Struktur der gesamten Rechnung
  - `customer`, `service`, `items`, `amount`, `invoice_number`, `issue_date`, …
- **`InvoiceItem`**: Einzelpositionen (Material, Arbeitszeit, Fahrt)
- **`Address`, `Customer`**: strukturierte Kundendaten
- **Extraktions‑Modelle** für LLM‑Output:
  - `ExtractionResult`, `CustomerPass`, `MaterialPass`, `LaborPass`, `TravelPass`
  - Mehrstufige Extraktion: Pass 1‑4

**Warum so viele Modelle?**

- `ExtractionResult` und Pass‑Modelle dienen der **strikten JSON‑Validierung**
  der LLM‑Antwort. Fehlerhafte Outputs werden abgefangen und repariert
  (`parse_model_json` in `app/models.py`, genutzt in `app/llm_agent.py`).

---

## 5) LLM‑Pipeline im Detail

### 5.1 `app/llm_agent.py`

**Provider**:

- `OpenAIProvider`: Chat‑Completions API
- `OllamaProvider`: lokales Ollama via HTTP

**Ablauf**:

1. **Pre‑Extraction** (`app/preextract.py`):
   Regex‑basierte Kandidatenliste (Material, Fahrt, Stunden, Adresse).
2. **Multi‑Pass‑Extraktion** (`_extract_multi_pass`):
   - Pass 1: Kunde & Adresse
   - Pass 2: Material
   - Pass 3: Arbeitszeit
   - Pass 4: Fahrtkosten
3. **Merge** der Pass‑Ergebnisse → `ExtractionResult`
4. **Validierung** fehlender Pflichtfelder (`missing_extraction_fields`)
5. Rückgabe als JSON‑String

**System Prompt** sorgt dafür, dass das LLM keine Felder „erfindet“ und die
Kandidatenliste bevorzugt (`SYSTEM_PROMPT`).

---

## 6) Deterministische Vorverarbeitung (Pre‑Extraction)

### 6.1 `app/preextract.py`

- **Material**: Regex‑Muster für Mengen + Preis + Beschreibung
- **Fahrtkosten**: Erkennung von Kilometerangaben
- **Arbeitszeit**: Erkennung von Meister/Geselle + Stunden
- **Adresse**: Erkennung von Straße/PLZ/Ort

Ergebnis ist ein `PreextractCandidates`‑Objekt, das dem LLM als Kontext
mitgegeben wird.

---

## 7) Speech‑to‑Text (STT)

### 7.1 `app/stt/`

Provider‑Auswahl via `STT_PROVIDER`:

- **`openai`** → Whisper API
- **`whisper`** → lokales Whisper
- **`command`** → CLI‑Tool (sicher geparst via `shlex`)

Zusätzliche Funktion:

- **Transkript‑Normalisierung**: Zahlwörter werden ersetzt und optional
  fehlerhafte Ausdrücke via `transcript_replacements.*` korrigiert.

---

## 8) OCR

### 8.1 `app/ocr.py`

Aktuell wird nur Tesseract unterstützt. `OCR_PROVIDER` wird aus der
Konfiguration gelesen. Das OCR‑Ergebnis wird wie ein normales Transkript in
`/process-image/` weiterverarbeitet.

---

## 9) Preislogik und Materialpreise

### 9.1 `app/pricing.py`

- **Automatische Preiszuweisung**: Fehlt ein Preis, wird er anhand der
  Kategorie (Material/Arbeitszeit/Fahrt) gesetzt.
- **MWSt‑Berechnung**: Netto → Steuer → Brutto
- **Rechnungsnummer**: Wird generiert, falls keine vorhanden ist

### 9.2 `app/materials.py`

- Default‑Materialpreise (z. B. Schrauben)
- Optionales Einlesen über `MATERIAL_PRICES_PATH`
- Dynamisches Nachlernen: Preise aus realen Rechnungen werden gespeichert.

---

## 10) Rechnungsartefakte (PDF + XML)

### 10.1 PDF (`app/pdf.py` + `app/invoice_template.py`)

- `format_invoice_lines` generiert Klartext‑Zeilen für den PDF‑Export
- Optionale PDF‑Vorlage (`INVOICE_TEMPLATE_PDF`) wird als Hintergrund genutzt

### 10.2 XML (`app/xrechnung.py`)

- Simplifizierte XRechnung‑ähnliche XML‑Struktur
- Noch nicht vollständig EN‑16931‑konform, aber ein Startpunkt

---

## 11) Persistierung und Artefakte

### 11.1 `app/persistence.py`

Alle Verarbeitungen werden unter `data/<timestamp>/` gespeichert:

- `audio.wav` (optional)
- `image.*` (optional)
- `transcript.json` und `transcript.txt`
- `invoice.json`
- `invoice.pdf`
- `invoice.xml`

Diese Artefakte sind über `/data/...` abrufbar (FastAPI StaticFiles).

---

## 12) Konversation, Korrekturen und Bestätigung

### 12.1 `app/conversation.py`

**Spezielle Logik für die Dialog‑UI**:

- Erkennen von **Korrekturbefehlen** (z. B. „Position 2 Menge 3“)
- Erkennen von **Kundennamen** aus dem Gespräch
- Erkennung von **Arbeitsstunden** für Rollen (Meister/Geselle/Azubi)
- Speicherung von Zwischenschritten und aktuellem Rechnungszustand

**Bestätigungspflicht**:

- Sobald alle Pflichtdaten vorliegen, erzeugt das System eine Zusammenfassung
  (`app.summaries.build_invoice_summary`).
- Erst nach Bestätigung wird die Rechnung finalisiert.

---

## 13) Telephony‑Integration

### 13.1 `app/telephony/`

- Dynamische Auswahl zwischen Twilio und Sipgate (`app/telephony/__init__.py`)
- Gemeinsame Logik in `app/telephony/common.py`
- Rückfragen solange Pflichtfelder fehlen

**Aufruf‑Modell**:

- Telefonanbieter startet Recording → Webhook liefert Audio‑URL → Audio wird
  heruntergeladen → STT → LLM → ggf. Rückfrage → Finalize

---

## 14) Template Engine (optional)

### 14.1 `app/template_engine.py`

Nutzt Sentence‑Embeddings + FAISS, um ähnliche Text‑Vorlagen zu finden.
Aktuell ist die Engine nicht im Hauptfluss verdrahtet, bietet aber eine
Basis für spätere „Vorlagen‑Matching“‑Features.

---

## 15) Konfiguration (.env / Umgebungsvariablen)

Die wichtigsten Schlüssel (siehe `app/settings.py` und `.env.example`):

- **LLM**: `LLM_PROVIDER`, `LLM_MODEL`, `OLLAMA_BASE_URL`, `OLLAMA_TIMEOUT`
- **STT**: `STT_PROVIDER`, `STT_MODEL`, `STT_PROMPT`, `STT_LANGUAGE`
- **OCR**: `OCR_PROVIDER`
- **Telephony**: `TELEPHONY_PROVIDER`
- **TTS**: `TTS_PROVIDER`, `ELEVENLABS_API_KEY`, `ENABLE_MANUAL_TTS`
- **Billing**: `BILLING_ADAPTER`, `MCP_ENDPOINT`, `ENABLE_MCP`
- **Preise & MwSt**: `TRAVEL_RATE_PER_KM`, `LABOR_RATE_*`, `MATERIAL_RATE_DEFAULT`, `VAT_RATE`
- **Rechnungs‑Header**: `SUPPLIER_NAME`, `SUPPLIER_ADDRESS`, etc.
- **PDF‑Vorlage**: `INVOICE_TEMPLATE_PDF`

---

## 16) Erweiterungspunkte

### 16.1 Neues LLM‑Backend hinzufügen

1. Neue Klasse in `app/llm_agent.py` erstellen (Subclass von `LLMProvider`).
2. In `_LLM_PROVIDERS` registrieren.
3. Per `LLM_PROVIDER` aktivieren.

### 16.2 Neues STT‑Backend hinzufügen

1. Provider‑Klasse in `app/stt/__init__.py` erstellen.
2. In `_STT_PROVIDERS` registrieren.
3. Per `STT_PROVIDER` aktivieren.

### 16.3 Neues Billing‑System integrieren

1. Klasse erstellen, die `BillingAdapter` implementiert.
2. Pfad in `BILLING_ADAPTER=module:Class` konfigurieren.

---

## 17) Troubleshooting‑Hinweise

- **LLM nicht erreichbar**: Beim Startup wird geprüft (`check_llm_backend`).
  Mit `FAIL_ON_LLM_UNAVAILABLE=1` kann der Start abgebrochen werden.
- **Whisper lokal**: Benötigt `ffmpeg` und `numpy`.
- **OCR**: Tesseract muss als System‑Binary verfügbar sein.

---

## 18) Wichtige Dateien als Einstieg

Wenn du den Code verstehen willst, starte hier:

1. `app/main.py` (Hauptflows + API)
2. `app/models.py` (Datenmodelle und Validierung)
3. `app/llm_agent.py` (LLM‑Integration)
4. `app/preextract.py` (Heuristiken)
5. `app/pricing.py` (Preisberechnung)
6. `app/persistence.py` (Artefakte & Speicherung)
7. `app/conversation.py` (Dialog‑Logik)
8. `app/telephony/` (Telefon‑Webhooks)

---

## 19) Glossar zentraler Begriffe

- **InvoiceContext**: Vollständiges Rechnungsobjekt der Anwendung.
- **ExtractionResult**: LLM‑Output in strengem Schema.
- **PreextractCandidates**: Heuristisch erkannte Kandidaten vor LLM‑Call.
- **Billing‑Adapter**: Klasse, die Rechnungsdaten an Fremdsysteme sendet.

---

## 20) Zusammenfassung

Die Handwerker‑App ist modular aufgebaut. STT, LLM, TTS und Billing sind klar
gekapselt, sodass du einzelne Komponenten austauschen oder erweitern kannst.
Der Kernfluss bleibt dabei stabil: **Audio/Text → Extraktion → Validierung →
Preislogik → Rechnung → Persistierung**. Mit der Konversation und den
Telephony‑Webhooks ist die Anwendung bereits für reale, mehrstufige Dialoge
ausgelegt.
