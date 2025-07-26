import logging
import inspect
import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import persistence

@pytest.fixture(autouse=True)
def log_test_start(request):
    doc = inspect.getdoc(request.node.obj) if hasattr(request.node, "obj") else None
    if doc:
        first_line = doc.splitlines()[0]
        logging.info(f"START {request.node.name} - {first_line}")
    else:
        logging.info(f"START {request.node.name}")
    yield
    logging.info(f"END {request.node.name}")


@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(persistence, "DATA_DIR", data_dir)
    data_dir.mkdir()
    yield data_dir
