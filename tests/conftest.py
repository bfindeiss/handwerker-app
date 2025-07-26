import logging
import pytest

@pytest.fixture(autouse=True)
def log_test_start(request):
    logging.info(f"START {request.node.name}")
    yield
    logging.info(f"END {request.node.name}")
