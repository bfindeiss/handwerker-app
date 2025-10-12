# Vortrag "Vibecoding im JVM-Land" – Foliensatz

## 1. Titel & Opener
- **Titel-Folie**: "Vibecoding im JVM-Land" – Vom autonomen Python-Prototyp zur produktionsreifen Java-Plattform
- Untertitel: "Spring AI vs. Quarkus + langchain4j im Angesicht von JDK 25"
- Sprechername, Funktion, Kontakt
- Key Visual: Pipeline von Audio → STT → LLM → Rechnung → Billing

## 2. Agenda
1. Vibecoding-Herkunft der App
2. Architektur des Python-Prototypen
3. Spring-AI-Umsetzung
4. Quarkus/langchain4j-Umsetzung
5. JDK-25-Neuerungen als Booster
6. Governance & Vibecoding-Delivery
7. Lessons Learned & Ausblick
8. Q&A

## 3. Story: Vibecoding-Herkunft
- Slide: "100 % KI-generiert" – Zeitstrahl der autonomen Entwicklung (Idee → Code → Tests → Deployment)
- Bullet: Keine menschliche Codezeile, Pipeline orchestriert durch Multi-Agenten-System
- Zitat-Folie: "Wir haben nur den Prompt gesetzt – den Rest erledigte die Maschine"
- Callout: Warum die Java-Welt skeptisch war (Compliance, Tooling, Langzeitpflege)

## 4. Ausgangslage Python-Prototyp
- Architekturdiagramm mit Komponenten (FastAPI, STT-Adapter, LLM-Agent, Billing, PDF)
- Tabelle: Funktion → Technologie → Herausforderungen (z. B. Skalierung, Monitoring)
- Highlight: Schnittstellen, die in Java nachgebaut werden müssen

## 5. Zielbild Spring Boot + Spring AI
- Folie: Komponentendiagramm (Controller, Services, Repositories, BillingAdapter)
- Bullet-Liste:
  - Spring AI ChatClient für LLM-Orchestrierung
  - Async/Reactive Verarbeitungs-Pipeline (Project Reactor)
  - PDF & Billing via iText/OpenPDF + REST Clients
- Code-Snippet-Slide: Beispiel `InvoiceAgentService` mit Prompt Template Injection
- Architektur-Überblick: Integration von Observability (Micrometer, Actuator) & Security (Spring Security)

## 6. Zielbild Quarkus + langchain4j
- Folie: Komponentendiagramm (RESTEasy Resource, Mutiny Pipeline, langchain4j Chains)
- Bullet-Liste:
  - @AiService Interface für strukturierte LLM-Outputs
  - Panache Entities für Rechnungen, Object Storage für Dateien
  - Native Mode Deployments für Functions/Edge
- Code-Snippet-Slide: `InvoiceAssistant` Interface mit `@AiService`
- Observability/Security: OpenTelemetry Exporter, Quarkus OIDC

## 7. Gegenüberstellung Spring vs. Quarkus
- Tabelle (Spalten: Kriterium, Spring AI, Quarkus/langchain4j)
- Punkte: Entwicklungs-Tooling, Performance, Native Builds, Community-Support
- Diagramm: Latenz & Memory-Footprint (Mock-Werte mit Trends)

## 8. JDK 25 als Gamechanger
- Slide: "Warum JDK 25 jetzt?"
- Bullet-Highlights:
  - Project Panama (FFM) für effiziente STT/LLM Native Calls
  - Loom-Optimierungen → Virtual Threads für parallele Pipelines
  - Security Defaults & Sandbox für autonomen Code
  - Pattern Matching & String Templates für kompakte Prompts
  - GraalVM/Mandrel-Synergie für kleinere Native Images
- Beispiel-Folie: Code-Vergleich String Templates für Prompt-Generierung

## 9. Governance & Vibecoding Delivery
- Prozess-Slide: Prompt-Governance → KI-Code-Generierung → Review-Automation → Deployment
- Risiko-Matrix: Rechtlich, Technisch, Operativ – Gegenmaßnahmen
- Compliance-Checkliste: Audit Trails, Secrets-Management, Observability

## 10. Automatisierte Delivery-Pipeline
- Diagramm: GitOps-Flow (Prompt-Repo → Agent → Build → Tests → Deployment)
- Fokus: Wie KI Agents Infrastruktur (Terraform/Helm) und Tests generieren
- Demo-Idee (optional): Git-Log vs. Agent-Log

## 11. Lessons Learned
- Drei-Spalten-Folie: "Was lief gut" / "Was hat überrascht" / "Was bleibt schwierig"
- Beispiele:
  - + Schnelle Iterationen dank KI
  - + Native Builds durch GraalVM auf JVM-Seite
  - Δ Prompt-Drift & Sicherheitsfreigaben
  - – Fehlende Human-in-the-loop-Checks können gefährlich sein

## 12. Ausblick
- Roadmap: Integration weiterer KI-Services (Vision, Dokumentenverständnis)
- Vibrant Conclusion: "Von Vibecoding zu Vibedelivery – der nächste Schritt"
- Call-to-Action: Community einbinden, Open-Source, Feedback-Kanal

## 13. Q&A & Backup
- Q&A-Slide mit Kontaktinfos & QR-Code zur Doku
- Backup-Slides:
  - Detail-Architektur der Billing-Adapter
  - Kostenkalkulation Cloud vs. On-Prem
  - Benchmark-Charts (Spring vs. Quarkus im Native Mode)

## 14. Appendix: Ressourcen & Links
- Verweise auf Repository, Architektur-Dokument, FFM/JDK25 Docs, langchain4j Guides
- Hinweis auf Open-Source-Policy & Contributor License Agreement

---
_Notiz für Speaker_: Jede Folie mit Storytelling-Hooks versehen (z. B. "Agent XY hat diese Entscheidung getroffen"), um den autonomen Ursprung lebendig zu halten.
