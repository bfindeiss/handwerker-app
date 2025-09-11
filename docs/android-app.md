# Android-App: Sprachaufnahmen mit LLM-Backend

Diese Anleitung beschreibt die native Android‑Anwendung der Handwerker‑App. Die App zeichnet Sprache über das Mikrofon auf,
sendet die Audiodatei an das FastAPI‑Backend (`/process-audio/`) und zeigt die vom LLM extrahierten
Rechnungsdaten an. Damit steht die LLM‑gestützte Fakturierung direkt auf dem Smartphone zur Verfügung.

## 1. Projektübersicht

Der Android‑Client befindet sich im Verzeichnis [`android/`](../android). Wichtigste Komponenten:

| Datei | Zweck |
| ----- | ----- |
| `android/build.gradle` | Top‑Level‑Gradle-Konfiguration |
| `android/settings.gradle` | Projektdefinition |
| `android/app/build.gradle` | Modulkonfiguration und Abhängigkeiten (u.a. OkHttp) |
| `android/app/src/main/AndroidManifest.xml` | Manifest mit Internet- und Mikrofonberechtigung |
| `android/app/src/main/java/com/handwerker/app/MainActivity.kt` | Kotlin-Code für Aufnahme und Upload |
| `android/app/src/main/res/layout/activity_main.xml` | Layout mit Aufnahmeknopf und Ergebnisanzeige |
| `android/app/src/main/res/values/strings.xml` | UI-Texte |

## 2. Voraussetzungen

- **Android Studio** (Giraffe oder neuer) mit aktuellem Android‑SDK
- **JDK 17** oder höher
- Laufender Backend‑Server der Handwerker‑App. Lokal kann er mit
  `uvicorn app.main:app --reload` gestartet werden.

## 3. Projekt in Android Studio öffnen

1. Android Studio starten und "**Open an existing project**" wählen.
2. Das Verzeichnis `android/` des Repositorys auswählen.
3. Beim ersten Import lädt Gradle automatisch alle Abhängigkeiten
   (Internetverbindung erforderlich).

## 4. API-Endpunkt konfigurieren

Der Basis-URL des Backends wird über **Product Flavors** gesteuert und zur Build-Zeit in
`BuildConfig.API_BASE_URL` geschrieben. Zwei Varianten sind vorkonfiguriert:

- `local` – nutzt `http://10.0.2.2:8000` für den Emulator (weitergereicht an `/process-audio/`).
- `remote` – verweist auf `https://example.com` und dient als Platzhalter für einen externen Server.

Im Fenster **Build Variants** von Android Studio lässt sich zwischen `localDebug` und
`remoteDebug` (bzw. Release-Pendants) umschalten. Für ein eigenes Backend einfach in
[`android/app/build.gradle`](../android/app/build.gradle) den Wert der entsprechenden
`buildConfigField`-Zeile anpassen.

## 5. App kompilieren und starten

1. In Android Studio **Build → Make Project** ausführen oder `Ctrl`+`F9` drücken.
2. Ein virtuelles Gerät (AVD) mit Android 10 oder neuer anlegen oder ein
   echtes Gerät per USB verbinden.
3. Über **Run → Run 'app'** die Anwendung starten.
4. Beim ersten Start fragt die App nach der Berechtigung für Mikrofonzugriff.
   Diese muss bestätigt werden.

## 6. Bedienung

1. **Aufnahme starten**: Auf den Button "Aufnahme starten" tippen.
   Der Text wechselt zu "Aufnahme stoppen" und das Mikrofon zeichnet auf.
2. **Aufnahme stoppen**: Den Button erneut antippen. Die Audiodatei wird
   lokal als M4A gespeichert und an `<api_base_url>/process-audio/`
   übertragen.
3. **Ergebnis ansehen**: Die Antwort des Backends (Transkript, Rechnungsdaten
   usw.) erscheint als JSON im unteren Textfeld.

Fehler (z. B. fehlende Verbindung) werden ebenfalls im Textfeld ausgegeben.

## 7. Funktionsweise

- Die Aufnahme erfolgt über `MediaRecorder` im Format MPEG‑4/AAC.
- Für den Netzwerktransport nutzt die App `OkHttp` und sendet die Datei als
  `multipart/form-data` (Feldname `file`).
- Das Backend wandelt die Audiodatei bei Bedarf in WAV um, führt
  Speech‑to‑Text durch und übergibt das Transkript an das konfigurierte LLM.
- Der LLM‑Output wird mit den berechneten Rechnungspositionen direkt
  an die App zurückgesendet.

## 8. Fehlerbehebung

| Problem | Lösung |
| ------- | ------ |
| Keine Mikrofonberechtigung | In den Android-Einstellungen der App die Berechtigung erteilen. |
| Netzwerkfehler | Basis-URL prüfen und sicherstellen, dass der Server erreichbar ist. |
| Antwort leer oder fehlerhaft | Server-Logs überprüfen; eventuell LLM-Backend nicht verfügbar. |

## 9. Weiterführende Anpassungen

- **Eigenes UI**: Layout und Texte lassen sich leicht erweitern,
  z. B. mit einer Fortschrittsanzeige oder einem JSON-Viewer.
- **Authentifizierung**: Bei Bedarf können HTTP-Header (z. B. API-Tokens)
  vor dem Upload gesetzt werden.
- **Offline-Modus**: Durch lokale Speicherung könnten Aufnahmen später
  gesammelt hochgeladen werden.

## 10. Lizenz

Der Android-Client steht unter denselben Lizenzbedingungen wie das
übrige Projekt. Beiträge und Verbesserungen sind als Pull Request willkommen.
