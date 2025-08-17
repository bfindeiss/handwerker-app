from pathlib import Path
import shutil

from app.models import InvoiceContext, InvoiceItem
from app.persistence import store_interaction, DATA_DIR


def _invoice():
    return InvoiceContext(
        type="InvoiceContext",
        customer={"name": "Max"},
        service={"description": "Arbeit"},
        items=[
            InvoiceItem(
                description="Schraube",
                category="material",
                quantity=1,
                unit="stk",
                unit_price=0,
            )
        ],
        amount={"net": 0, "tax": 0, "total": 0, "currency": "EUR"},
    )


def test_store_interaction_creates_xrechnung(tmp_path):
    # Ensure DATA_DIR points to temporary directory for test isolation
    original_data_dir = DATA_DIR.resolve()
    try:
        # Redirect DATA_DIR to tmp_path
        import app.persistence as persistence_module

        persistence_module.DATA_DIR = tmp_path
        persistence_module.DATA_DIR.mkdir(exist_ok=True)

        session_path = store_interaction(b"", "test", _invoice())
        xml_path = Path(session_path) / "invoice.xml"
        assert xml_path.exists()
    finally:
        # Cleanup any created directories
        shutil.rmtree(tmp_path, ignore_errors=True)
        persistence_module.DATA_DIR = original_data_dir
