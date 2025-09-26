# Analyse der Benutzereingabe- und Rechnungsverarbeitung

## Beobachtete Schwächen

- **Starre Platzhalter-Rechnung bei Parserfehlern:** Wenn das LLM keinen gültigen JSON-Kontext liefert, baut `conversation._handle_conversation` eine Default-Rechnung mit "Arbeitszeit Geselle", generischem "Material" und einer Anfahrt auf. Anschließend überschreibt `apply_pricing` die Preise mit festen Standardsätzen. Dadurch wirkt jede Interaktion gleichförmig, selbst wenn der Nutzer andere Leistungen beschreibt.【F:app/conversation.py†L108-L165】【F:app/pricing.py†L12-L44】
- **Begrenzte Materialerkennung:** Das Material-Preisverzeichnis umfasst nur drei Stichwörter. Neue Materialien, die das LLM erkennt, laufen daher in `_apply_item_price` entweder in eine HTTP-Fehlermeldung oder werden mit einem pauschalen Standardpreis bewertet, sofern `material_rate_default` gesetzt ist. Individualisierte Materialangaben aus der Benutzereingabe gehen so verloren.【F:app/materials.py†L1-L20】【F:app/pricing.py†L47-L71】
- **Rollenverwechslung bei Arbeitszeiten:** Arbeitspositionen erhalten lediglich über das optionale Feld `worker_role` den Hinweis auf Geselle/Meister. Fehlt dieses Attribut in der LLM-Antwort, fällt `_apply_item_price` auf den Default-Satz zurück; `estimate_labor_item` erzeugt generell "Arbeitszeit Geselle". Selbst wenn der Nutzer Meisterstunden nennt, wird der Gesellenplatzhalter beibehalten, solange keine eindeutige Rolle erkannt wird.【F:app/service_estimations.py†L11-L33】【F:app/pricing.py†L47-L63】
- **Heuristische Kategorien führen zu Überschreibungen:** `parse_invoice_context` klassifiziert Positionen anhand weniger Schlüsselwörter. Materialeinträge mit Begriffen wie "Fahrtkosten" werden als Reisezeit erkannt und verlieren so individuelle Preise; Reise- oder Arbeitspositionen ohne klare Schlüsselwörter werden automatisch als Material behandelt.【F:app/models.py†L55-L96】
- **Mengen/Preise werden nachträglich überschrieben:** `merge_invoice_data` ersetzt Placeholder zwar, aber `apply_pricing` setzt für Reisen und teilweise für Lohnarbeiten immer die Defaults – selbst wenn das LLM bereits andere Sätze geliefert hat. So verschwinden benutzerdefinierte Anpassungen wieder aus der Rechnung.【F:app/conversation.py†L58-L118】【F:app/pricing.py†L19-L63】

## Auswirkungen auf die Flexibilität

1. **Neue Materialtypen** werden nicht sauber übernommen, weil weder das Materialverzeichnis noch die Preislogik dynamisch sind. Die Anwendung zwingt die Ausgabe in bekannte Kategorien und Tarife, was zu generischen Rechnungen führt.
2. **Spezifische Lohnrollen** (Meister vs. Geselle) lassen sich nicht zuverlässig unterscheiden. Ohne exakte Nennung von "Meister" im Text fällt die Pipeline auf den Default zurück.
3. **Benutzerdefinierte Preise** aus der Eingabe verlieren ihre Wirkung, weil die Nachbearbeitung sie überschreibt oder mittels Standardwerten ersetzt.

## Empfohlene Gegenmaßnahmen

- **LLM-Ausgabe konservativer übernehmen:** Nur dann `apply_pricing` anwenden, wenn Preisfelder komplett fehlen, anstatt bestehende Preise grundsätzlich zu überschreiben. Zusätzlich Travel-Preise nur ergänzen, wenn keine Angabe vorliegt.
- **Materialdaten erweitern oder externisieren:** Preisnachschlagewerk dynamisch halten (z. B. Konfiguration oder Datenbank), damit neue Materialien mit Nutzerpreisen zusammen bestehen können.
- **Rollenerkennung verbessern:** Nutzerinput gezielt nach "Meister", "Geselle", "Azubi" usw. durchsuchen und den Treffer in `worker_role` übernehmen. Alternativ rollenspezifische Fragen stellen, wenn mehrere Varianten vorkommen.
- **Heuristiken verfeinern:** Kategorien nicht nur über Schlüsselwörter, sondern auch über originale LLM-Klassifikation oder strukturierte Bestätigung vom Nutzer bestimmen, um Fehlklassifikationen zu vermeiden.
- **Fehlerfall-Handling modularisieren:** Die Default-Rechnung sollte nur ein Zwischenergebnis sein und klar als solche kommuniziert werden, statt sofort als finale Rechnung mit Standardpreisen zu erscheinen.
