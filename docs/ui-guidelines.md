# UI-Guidelines

## TTS-Steuerung in der Weboberfläche

- Die Weboberfläche nutzt die native Web Speech API (`speechSynthesis`).
- TTS wird **nur** per Button ausgelöst:
  - **▶️ Start Vorlesen**: gibt den letzten Bot-Text aus.
  - **⏸️ Pause**: pausiert die aktuelle Ausgabe.
  - **⏹️ Stop Vorlesen**: beendet die Ausgabe vollständig.
- Wenn `ENABLE_MANUAL_TTS=false` gesetzt ist, wird das frühere automatische Abspielen wieder aktiviert.

## Minimaler Sprechstil (Backend-TTS)

- Kurze, funktionale Sätze ohne Begrüßungen oder Floskeln.
- Maximal zwei Sätze pro Statusmeldung.
- Fokus auf Fakten: Kunde, Leistung, Positionen, Gesamtbetrag.

