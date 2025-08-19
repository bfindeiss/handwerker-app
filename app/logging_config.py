import logging

from app.request_id import RequestIdFilter


def configure_logging() -> None:
    """Setzt ein einfaches Logging-Format für die gesamte Anwendung."""
    # ``basicConfig`` reicht hier aus – es erstellt automatisch einen Root-Logger
    # und schreibt Nachrichten auf die Konsole.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] [%(request_id)s] %(message)s",
    )
    logging.getLogger().addFilter(RequestIdFilter())
