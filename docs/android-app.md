# Android-App: Weboberfläche als mobile Anwendung

Diese Dokumentation beschreibt, wie die Weboberfläche der Handwerker-App als
native Android‑Anwendung bereitgestellt wird. Der Android‑Client besteht aus
einer einzigen Activity mit einem `WebView`, der die bestehende Webseite
(`web`‑Frontend des FastAPI‑Servers) lädt. So können Handwerker die Oberfläche
komfortabel auf Smartphones und Tablets nutzen, ohne einen mobilen Browser zu
starten.

## 1. Projektstruktur

Der Android‑Code liegt im Verzeichnis [`android/`](../android). Das Projekt ist
unabhängig vom Python‑Backend und kann separat in **Android Studio** geöffnet
werden. Die wichtigsten Dateien sind:

| Datei | Zweck |
| ----- | ----- |
| `android/build.gradle` | Top‑Level‑Gradle‑Konfiguration |
| `android/settings.gradle` | Definition des Projekt‑ und Modulnamens |
| `android/app/build.gradle` | Modulkonfiguration (SDK‑Versionen, Abhängigkeiten) |
| `android/app/src/main/AndroidManifest.xml` | Manifest mit `MainActivity` |
| `android/app/src/main/java/com/handwerker/app/MainActivity.kt` | Kotlin‑Code für den `WebView` |
| `android/app/src/main/res/layout/activity_main.xml` | Layout mit einem `WebView` |
| `android/app/src/main/res/values/strings.xml` | Enthält `web_app_url` – die zu ladende Webseite |

## 2. Voraussetzungen

- **Android Studio** (Giraffe oder neuer) mit aktuellem Android‑SDK
- **JDK 17** oder höher
- Laufender Backend‑Server der Handwerker‑App. Für lokale Tests kann er mit
  `uvicorn app.main:app --reload` gestartet werden.

## 3. Projekt in Android Studio öffnen

1. Android Studio starten und "**Open an existing project**" wählen.
2. Das Verzeichnis `android/` innerhalb des Repositorys auswählen.
3. Beim ersten Import lädt Gradle automatisch die benötigten Plugins und
   Abhängigkeiten. Eine aktive Internetverbindung ist erforderlich.

## 4. URL der Weboberfläche anpassen

Standardmäßig lädt die App im Emulator die lokale Entwicklungsinstanz über
`http://10.0.2.2:8000/web`. Für echte Geräte oder Produktionssysteme muss die
URL angepasst werden:

1. Datei [`android/app/src/main/res/values/strings.xml`](../android/app/src/main/res/values/strings.xml) öffnen.
2. Den Wert von `<string name="web_app_url">` auf die gewünschte Adresse ändern,
   z. B. `https://mein-server.de/web`.
3. Projekt neu kompilieren, damit der String im APK enthalten ist.

Alternativ kann die URL auch zur Laufzeit über `BuildConfig` gesteuert werden.
Dazu in `android/app/build.gradle` einen `buildConfigField` ergänzen und in
`MainActivity` auf `BuildConfig.WEB_APP_URL` zugreifen.

## 5. App kompilieren und starten

1. Im Menü **Build → Make Project** wählen oder `Ctrl` + `F9` drücken.
2. Bei Verwendung des Emulators: Ein virtuelles Gerät (AVD) mit Android 10 oder
   neuer anlegen.
3. Über **Run → Run 'app'** die Anwendung auf dem Emulator oder einem
   angeschlossenen Gerät starten.
4. Der `WebView` lädt automatisch die konfigurierte URL und zeigt die bekannte
   Weboberfläche an.

## 6. Funktionsumfang

- Vollständige Darstellung der Weboberfläche innerhalb der App
- JavaScript und Local‑Storage sind aktiviert, damit alle Frontend‑Funktionen
  wie im Browser zur Verfügung stehen
- Die Zurück‑Navigation des Betriebssystems schließt die App (kein History‑Stack)

## 7. Fehlerbehebung

| Problem | Lösung |
| ------- | ------ |
| Seite bleibt leer | Prüfen, ob der Server unter der konfigurierten URL erreichbar ist. |
| "Webpage not available" | Internet‑Berechtigung im Manifest wird automatisch gesetzt; dennoch sollte eine aktive Verbindung bestehen. |
| Mixed‑Content‑Warnung | Für produktive Umgebungen sollte HTTPS verwendet werden. |

## 8. Weiterführende Anpassungen

- **Eigene App‑Icons**: In `app/src/main/res/mipmap-*/` können benutzerdefinierte
  Icons abgelegt werden.
- **Offline‑Modus**: Der `WebView` lädt standardmäßig Online‑Inhalte. Für einen
  Offline‑Betrieb müssten die HTML‑Dateien lokal gebündelt werden.
- **Back‑Navigation im WebView**: Durch Überschreiben von `onBackPressed()` in
  `MainActivity` kann das Navigationsverhalten angepasst werden.

## 9. Lizenz

Der Android‑Client folgt denselben Lizenzbedingungen wie das restliche Projekt.
Änderungen oder Weiterentwicklungen sollten als Pull Request in dieses
Repository eingebracht werden.

