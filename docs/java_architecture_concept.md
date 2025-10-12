# Konzept: Java-basierte Weiterentwicklung des Sprachassistenten für Handwerker

## 1. Ausgangslage

Das bestehende System basiert auf FastAPI (Python) und orchestriert Speech-to-Text, Large Language Model (LLM) sowie Rechnungs- und PDF-Services. Kernelemente sind:

- `app/main.py`: FastAPI-Anwendung mit Upload-Endpunkt für Audio.【F:README.md†L19-L27】
- `app/llm_agent.py`: Prompt- und LLM-Steuerung inkl. Auswahl unterschiedlicher Anbieter.【F:README.md†L21-L31】
- `app/stt/`: Abstraktionsschicht für diverse Speech-to-Text-Dienste.【F:README.md†L21-L31】
- `app/billing_adapter.py` & `billing_adapters/`: Anbindung an externe Rechnungssysteme.【F:README.md†L21-L31】
- Persistenz und PDF-Generierung über `app/persistence.py`, `app/pdf.py`, `app/invoice_template.py` u. a.

Die Architektur folgt einer modularen Servicestruktur mit austauschbaren Backends. Deployment erfolgt u. a. per Docker, AWS Lambda oder Render; optional steht eine Android-App für Sprachaufnahmen bereit.【F:README.md†L1-L108】

## 2. Java-Umsetzung mit Spring Boot & Spring AI

### 2.1 Zielbild
Eine Java/Spring-Variante soll die Python-Logik spiegeln, die Integration in Java-Ökosysteme erleichtern und Compliance-Anforderungen (z. B. unternehmenseigene JVM-Stacks) adressieren.

### 2.2 Architekturkomponenten
1. **Spring Boot REST-API**
   - Controller `AudioProcessingController` mit Endpunkt `POST /process-audio` (Multipart).
   - Async Eventing via `@Async` oder Reactor, um STT und LLM-Aufrufe nicht-blockierend zu gestalten.

2. **Speech-to-Text Service**
   - Interface `SpeechToTextService` mit Implementierungen für Whisper (lokal via JNI/FFmpeg), OpenAI, ggf. Deepgram.
   - Nutzung von Spring AI `ChatClient` für Cloud-gestützte Transkription oder Anbindung eines dedizierten STT-Adapters.

3. **LLM Orchestrierung**
   - `InvoiceAgentService`, der via Spring AI `ChatClient` strukturierte Prompts zusammenstellt.
   - Prompt-Templates in separaten YAML/Markdown-Dateien, Injection über Spring ConfigurationProperties.

4. **Domänenmodell & Validierung**
   - Java Records/Classes für `InvoiceContext`, `Position`, `MaterialPosten` etc., Validierung via Bean Validation (Jakarta Validation).

5. **Rechnungs-Workflow**
   - `BillingAdapter` Interface; Implementierungen für Dateiablage, sevDesk (per REST), DATEV (SOAP/REST), etc.
   - Verwendung von Spring Batch oder einfachen Service-Klassen für PDF-Erzeugung (iText, OpenPDF).

6. **Persistenz & Audit**
   - Speicherung von Audio, Transkript, JSON in S3/minio oder lokalem Filesystem via Spring `ResourceLoader`.
   - Optional relationales Schema (PostgreSQL) mit JPA für Rechnungen, Audios, Events.

7. **Observability & Sicherheit**
   - Micrometer/Prometheus für Metriken, Spring Cloud Sleuth/Zipkin für Tracing.
   - AuthN via Spring Security (API Keys, OAuth2). Rate Limiting per Bucket4j.

### 2.3 Deployment
- Containerisiert (Docker, Buildpacks) oder als native Image via GraalVM Native Build Tools.
- Integration in bestehende CI/CD (GitHub Actions, Jenkins). Konfigurierbar über Spring Profiles.

## 3. Java-Umsetzung mit Quarkus & langchain4j

### 3.1 Zielbild
Quarkus ermöglicht geringe Startzeiten und geringen Footprint – passend für Cloud Functions oder serverlose Deployments (AWS Lambda, Knative). Langchain4j bietet LLM-Orchestrierung analog zur Python-Implementierung.

### 3.2 Architekturkomponenten
1. **HTTP Layer**
   - RESTEasy Reactive Resource `@Path("/process-audio")`, Multipart-Support.
   - Mutiny für reaktive Pipelines (Streaming von Audio-Transkription zu LLM).

2. **Speech-to-Text**
   - Service `SttService` mit Implementierungen für lokale Whisper-Java-Bindings oder Cloud STT (über REST-Clients mit Quarkus REST Client Reactive).
   - Optional Integration mit `langchain4j` Audio-Module (sofern verfügbar) oder eigener Adapter.

3. **LLM Orchestrierung mit langchain4j**
   - Definition eines `@AiService` Interface `InvoiceAssistant`, das Prompt-Templates und Output Parser für strukturierte Daten verwendet.
   - Nutzung von langchain4j Chains (z. B. ConversationalChain, StructuredOutputParser) zur Extraktion der Rechnungsdaten.

4. **Domänenlogik & Persistenz**
   - JPA/Hibernate ORM oder Panache Entity/Repository für Rechnungsdaten.
   - Speicherung von Dateien via `io.quarkus.vertx.http.runtime.VertxHttpRecorder` (non-blocking filesystem) oder S3 über Quarkus S3 Client.

5. **Billing-Adapter**
   - `BillingAdapter` Interface, Implementierungen als Quarkus CDI Beans (`@ApplicationScoped`).
   - REST- oder SOAP-Anbindungen mit Quarkus `RestClient` oder Camel Quarkus.

6. **PDF & Dokumentenerzeugung**
   - PDFBox/iText via Quarkus Extension, optional Serverless JasperReports.

7. **Observability & Sicherheit**
   - Quarkus Micrometer Extension, OpenTelemetry Exporter.
   - Auth über Quarkus OIDC oder API-Key Mechanismen.

### 3.3 Deployment
- Quarkus JVM Mode für Standard-Container, Native Mode (GraalVM/Mandrel) für minimale Latenz.
- Serverless Targets (AWS Lambda, Azure Functions) über Quarkus Extensions.

## 4. Vergleich zur aktuellen Python-Implementierung

| Aspekt | Aktuelles System (FastAPI/Python) | Spring AI Variante | Quarkus/langchain4j Variante |
| --- | --- | --- | --- |
| Sprache/Ökosystem | Python, FastAPI, Pydantic, AsyncIO | Java, Spring Boot, Spring AI | Java, Quarkus, langchain4j |
| LLM-Orchestrierung | Custom Prompting in `llm_agent.py` | Spring AI `ChatClient` + Prompt Templates | langchain4j Chains & `@AiService` |
| STT | Module unter `app/stt/` (Whisper, OpenAI, etc.) | `SpeechToTextService` mit Strategie-Pattern, Nutzung Spring AI oder REST-Clients | Reaktive STT-Services mit Mutiny/REST Client |
| Billing | Adapter-Pattern mit Python-Modulen | `BillingAdapter` Beans, Integration über Spring Cloud/OpenFeign | CDI-basierte Adapter, Quarkus REST Client |
| Persistenz | Filesystem + optionale DB | Spring Data JPA + Object Storage | Panache/JPA + Object Storage |
| Deployment | Docker, Lambda (Python Runtime), Render | Docker/Buildpacks, Spring Native, Kubernetes | Docker, Quarkus Native, Serverless Extensions |
| Observability | Logging + optionale Tools | Micrometer, Actuator, Spring Security | Micrometer Extension, OTel, Quarkus Security |
| Vibecoding-Faktor | Vollständige Automatisierung der App-Entwicklung bereits realisiert | Fokus auf MLOps-Automation (Code-Gen, IaC, Tests) mit Java-Tooling | Betonung auf Native-Build-Pipeline & GitOps zur Sicherstellung menschenfreier Delivery |

## 5. Vortrag: Idee & Abstract

### Idee
"Vibecoding im JVM-Land: Wie ein autonomer Sprachassistent vom Python-Prototyp zur produktionsreifen Java-Plattform reift" – Ein Erfahrungsbericht, wie vollständig KI-generierte Artefakte (Code, Tests, Infrastruktur) in Enterprise-Java-Stacks übertragen werden können, inklusive Lessons Learned zu Sicherheit, Compliance und Developer Experience.

### Abstract (Deutsch, ~1.300 Zeichen)

> Die Handwerker-App für sprachgesteuerte Rechnungen entstand ohne eine Zeile menschlich geschriebenen Codes – pure Vibecoding-Power! Doch was passiert, wenn wir diesen autonomen Prototypen in etablierte Java-Landschaften überführen müssen? In meinem Vortrag zeige ich, wie wir den bestehenden FastAPI/Python-Stack systematisch auf Spring Boot mit Spring AI sowie auf Quarkus mit langchain4j abbilden. Wir sprechen über Architekturmuster für Speech-to-Text, LLM-Orchestrierung und Billing-Workflows, über native Builds und serverlose Deployments – und über Governance-Fragen, wenn KI nicht nur Anwendungen, sondern auch deren Rollout steuert. Wer wissen möchte, wie sich vollständige Automatisierung mit Enterprise-Anforderungen vereinen lässt, bekommt hier das Praxis-How-to: von Prompt-Design über Observability bis zur API-Sicherheit. Das Ergebnis: Zwei JVM-Implementierungswege, die den Vibecoding-Spirit bewahren und gleichzeitig die Brücke zur Java-Welt schlagen.

