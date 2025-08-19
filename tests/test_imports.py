def test_import_service_estimations():
    import app.service_estimations as se
    assert hasattr(se, "estimate_invoice_items")
