import logging
import inspect
import pytest

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
