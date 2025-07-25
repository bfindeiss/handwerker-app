# Projekt: Sprachassistent für Handwerker (Telefon → Rechnung)

## Ziel
Entwicklung eines modularen Sprachassistenzsystems, das Telefongespräche mit Handwerkern verarbeitet, in strukturierte Daten umwandelt (z. B. Rechnungsdaten), diese mit CRM-/ERP-Systemen integriert und sich leicht erweitern lässt. Ziel ist ein hybrider Agent mit natürlicher Spracheingabe via Telefon, optional später auch Text.

---

## Systemkomponenten

### 1. Telefonie-Schnittstelle
- **Ziel:** Annahme und Abwicklung von Telefongesprächen
- **Technologien:** Twilio, SIP-Bridge, Asterisk
- **Funktionen:**
  - Anruf entgegennehmen/weiterleiten
  - Audio-Stream oder Aufnahme speichern (WAV/MP3)

### 2. Sprachverarbeitung
- **Ziel:** Umwandlung von Sprache in Text und zurück
- **Technologien:** 
  - Speech-to-Text: Whisper, Google STT, Deepgram
  - Text-to-Speech: ElevenLabs, Google TTS
- **Funktionen:**
  - Echtzeit-Transkription eingehender Sprache
  - Sprachausgabe für Rückantworten

### 3. LLM-Agent
- **Ziel:** Interpretation und Strukturierung der Gesprächsinhalte
- **Technologien:** OpenAI GPT-4o, Ollama + LangChain, Local LLMs
- **Funktionen:**
  - Kontextuelles Verstehen von Eingaben
  - Extraktion strukturierter Informationen (z. B. Kundendaten, Leistungen)
  - Ausgabe als JSON gemäß interner Modellstruktur (MCP-kompatibel)

### 4. API- und Systemintegration
- **Ziel:** Anbindung an externe Systeme wie CRM, ERP, Rechnungstools
- **Beispiele:** sevDesk, Lexoffice, Salesforce, Meisterbüro, Craftnote
- **Funktionen:**
  - Einbindung über Adapter mit abstrakten Schnittstellen
  - Nutzung modellkonformer Protokolle (MCP) statt hardcoded APIs

### 5. Persistenz und Protokollierung
- **Ziel:** Speicherung aller relevanten Kommunikations- und Rechnungsdaten
- **Funktionen:**
  - Speicherung von Transkripten, Audio-Dateien, JSON-Ausgaben
  - Revisionssicheres Logging (z. B. Audit-Trail)
  - Optionale Langzeitspeicherung / Archivierung (DSGVO-konform)

---

## Beispiel-Ablauf

1. Handwerker ruft an.
2. System nimmt Anruf entgegen, beginnt Transkription.
3. Handwerker sagt:  
   _„Ich brauch bitte eine Rechnung für Frau Müller – Badezimmer renoviert – 3.500 Euro inklusive Material.“_
4. LLM erzeugt folgenden Kontext (MCP-basiert):

```json
{
  "type": "InvoiceContext",
  "customer": {
    "name": "Frau Müller"
  },
  "service": {
    "description": "Badezimmer renoviert",
    "materialIncluded": true
  },
  "amount": {
    "total": 3500,
    "currency": "EUR"
  }
}
```

5. Der Kontext wird über eine standardisierte Schnittstelle an das gewünschte Rechnungsprogramm weitergegeben.  
6. Das System antwortet per TTS:  
   _"Die Rechnung für Frau Müller über 3.500 Euro wurde erstellt."_

---

## Nichtfunktionale Anforderungen (NFAs)

- **Datenschutz:**  
  - DSGVO-konforme Speicherung und Verarbeitung aller Gesprächs- und Kundendaten  
  - Möglichkeit zur anonymisierten Analyse

- **Multitenancy:**  
  - Gleichzeitige Nutzung durch mehrere Betriebe  
  - Isolation von Nutzerdaten

- **Maximale Flexibilität:**  
  - Austauschbarkeit aller Komponenten über definierte Schnittstellen  
  - Unterstützung mehrerer LLMs, STT/TTS-Systeme und API-Anbieter  
  - Adapter/Plugin-Architektur zur Erweiterung

- **Abstraktion der Schnittstellen:**  
  - Klare Trennung zwischen interner Logik und externer Anbindung  
  - Verwendung eines modellgetriebenen Ansatzes zur Beschreibung des Kontexts  
  - Schnittstellen sollen **MCP-kompatibel (Model Context Protocol)** sein, um externe Rechnungs- und CRM-Systeme modellbasiert ansprechen zu können

- **Erweiterbarkeit:**  
  - Erweiterung um weitere Ein- und Ausgabekanäle (z. B. Webchat, WhatsApp)  
  - Anpassbare Antwortlogik und Gesprächsführung je nach Mandant

- **Protokollierung:**  
  - Vollständige Gesprächshistorie (Text + Audio)  
  - Revisionssichere Speicherung der generierten Daten (Rechnungen, Kundendaten)
