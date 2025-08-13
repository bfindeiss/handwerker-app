import logging


def configure_logging() -> None:
    """Setzt ein einfaches Logging-Format für die gesamte Anwendung."""
    # ``basicConfig`` reicht hier aus – es erstellt automatisch einen Root-Logger
    # und schreibt Nachrichten auf die Konsole.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
