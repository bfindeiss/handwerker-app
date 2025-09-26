"""Load the handwerker-app knowledge graph into a Neo4j database.

The script reflects the architecture and business processes described in the
previous knowledge graph summary.  It uses the official Neo4j Python driver to
create/merge the nodes and relationships.
"""
from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass, field
from typing import Dict, Iterable, List

from neo4j import GraphDatabase


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Node:
    """Representation of a graph node."""

    key: str
    labels: Iterable[str]
    properties: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Relationship:
    """Representation of a graph relationship."""

    start: str
    end: str
    type: str
    properties: Dict[str, str] = field(default_factory=dict)


NODES: List[Node] = [
    Node(
        key="FastAPIApp",
        labels=["Component", "FastAPI"],
        properties={
            "name": "FastAPI app.main",
            "description": "Application entry point exposing REST and webhook routes.",
        },
    ),
    Node(
        key="ProcessAudioEndpoint",
        labels=["Endpoint", "HTTP"],
        properties={
            "name": "POST /process-audio/",
            "description": "Uploads audio, triggers STT and LLM pipeline, stores results.",
        },
    ),
    Node(
        key="ConversationRouter",
        labels=["Endpoint", "Conversation"],
        properties={
            "name": "Conversation router",
            "description": "Manages multi-turn dialogue, sessions and TTS responses.",
        },
    ),
    Node(
        key="TelephonyRouter",
        labels=["Endpoint", "Telephony"],
        properties={
            "name": "Telephony router",
            "description": "Handles Twilio/Sipgate webhooks and asynchronous audio downloads.",
        },
    ),
    Node(
        key="STTService",
        labels=["Service", "STT"],
        properties={
            "name": "Speech-to-Text",
            "description": "Transcribes audio recordings to text.",
        },
    ),
    Node(
        key="TranscriptArtifact",
        labels=["Artifact"],
        properties={
            "name": "Transcript",
            "description": "Text representation of recorded audio.",
        },
    ),
    Node(
        key="LLMService",
        labels=["Service", "LLM"],
        properties={
            "name": "LLM extraction",
            "description": "Extracts structured invoice context from transcripts.",
        },
    ),
    Node(
        key="InvoiceContext",
        labels=["Domain", "Invoice"],
        properties={
            "name": "InvoiceContext",
            "description": "Normalized invoice with customer, items, totals, and metadata.",
        },
    ),
    Node(
        key="PricingService",
        labels=["Service", "Pricing"],
        properties={
            "name": "Pricing engine",
            "description": "Applies default rates, taxes, and totals to invoice items.",
        },
    ),
    Node(
        key="BillingAdapter",
        labels=["Service", "Integration"],
        properties={
            "name": "Billing adapter",
            "description": "Sends invoices to downstream billing systems.",
        },
    ),
    Node(
        key="PersistenceService",
        labels=["Service", "Persistence"],
        properties={
            "name": "Persistence",
            "description": "Stores transcripts, PDFs, XML exports, and audio artifacts.",
        },
    ),
    Node(
        key="PDFGenerator",
        labels=["Artifact", "PDF"],
        properties={
            "name": "PDF generator",
            "description": "Produces invoice PDFs using ReportLab templates.",
        },
    ),
    Node(
        key="XRechnungGenerator",
        labels=["Artifact", "XML"],
        properties={
            "name": "XRechnung generator",
            "description": "Creates simplified XRechnung XML output.",
        },
    ),
    Node(
        key="TTSServices",
        labels=["Service", "TTS"],
        properties={
            "name": "Text-to-Speech",
            "description": "Generates spoken responses for dialogues and callbacks.",
        },
    ),
    Node(
        key="TelephonyIntegrations",
        labels=["Integration", "Telephony"],
        properties={
            "name": "Twilio & Sipgate integrations",
            "description": "Download recordings and trigger processing pipeline.",
        },
    ),
    Node(
        key="Downloader",
        labels=["Service", "Utility"],
        properties={
            "name": "Recording downloader",
            "description": "Fetches remote call recordings asynchronously.",
        },
    ),
]


RELATIONSHIPS: List[Relationship] = [
    Relationship("FastAPIApp", "ProcessAudioEndpoint", "EXPOSES"),
    Relationship("FastAPIApp", "ConversationRouter", "EXPOSES"),
    Relationship("FastAPIApp", "TelephonyRouter", "EXPOSES"),
    Relationship("ProcessAudioEndpoint", "STTService", "USES"),
    Relationship("ProcessAudioEndpoint", "LLMService", "USES"),
    Relationship("ProcessAudioEndpoint", "InvoiceContext", "CREATES"),
    Relationship("ProcessAudioEndpoint", "PersistenceService", "PERSISTS"),
    Relationship("STTService", "TranscriptArtifact", "PRODUCES"),
    Relationship("LLMService", "InvoiceContext", "ENRICHES"),
    Relationship("InvoiceContext", "PricingService", "USES"),
    Relationship("InvoiceContext", "BillingAdapter", "DISPATCHES_TO"),
    Relationship("PersistenceService", "TranscriptArtifact", "STORES"),
    Relationship("PersistenceService", "PDFGenerator", "STORES"),
    Relationship("PersistenceService", "XRechnungGenerator", "STORES"),
    Relationship("ConversationRouter", "STTService", "USES"),
    Relationship("ConversationRouter", "LLMService", "USES"),
    Relationship("ConversationRouter", "InvoiceContext", "UPDATES"),
    Relationship("ConversationRouter", "TTSServices", "USES"),
    Relationship("TelephonyRouter", "TelephonyIntegrations", "DELEGATES_TO"),
    Relationship("TelephonyRouter", "Downloader", "USES"),
    Relationship("TelephonyRouter", "STTService", "USES"),
    Relationship("TelephonyRouter", "LLMService", "USES"),
    Relationship("TelephonyRouter", "InvoiceContext", "USES"),
    Relationship("TelephonyRouter", "PersistenceService", "USES"),
]


def _merge_node(tx, node: Node) -> None:
    labels = ":".join(node.labels)
    query = (
        f"MERGE (n:{labels} {{key: $key}}) "
        "SET n += $properties"
    )
    tx.run(query, key=node.key, properties=node.properties)


def _merge_relationship(tx, rel: Relationship) -> None:
    query = (
        "MATCH (start {key: $start_key}) "
        "MATCH (end {key: $end_key}) "
        "MERGE (start)-[r:%s]->(end) "
        "SET r += $properties"
    ) % rel.type
    tx.run(query, start_key=rel.start, end_key=rel.end, properties=rel.properties)


def load_graph(uri: str, user: str, password: str) -> None:
    """Load graph metadata into Neo4j."""

    driver = GraphDatabase.driver(uri, auth=(user, password))
    LOGGER.info("Connecting to %s", uri)
    with driver, driver.session() as session:
        session.execute_write(lambda tx: [_merge_node(tx, node) for node in NODES])
        session.execute_write(
            lambda tx: [_merge_relationship(tx, rel) for rel in RELATIONSHIPS]
        )
    LOGGER.info("Graph successfully loaded.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("uri", help="Neo4j bolt URI, e.g. bolt://localhost:7687")
    parser.add_argument("user", help="Neo4j username")
    parser.add_argument("password", help="Neo4j password")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging verbosity.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))
    load_graph(args.uri, args.user, args.password)


if __name__ == "__main__":
    main()
