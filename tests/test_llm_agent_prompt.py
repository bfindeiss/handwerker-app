import re

from app.llm_agent import _build_prompt


def test_build_prompt_preserves_quotes():
    transcript = 'Er sagte "Hallo" und "Tschüss"'
    prompt = _build_prompt(transcript)
    assert transcript in prompt
    # Ensure there are no extraneous surrounding quotes around transcript
    # preceding and following context should match expected format
    assert re.search(r"Text:\nEr sagte \"Hallo\" und \"Tschüss\"\n", prompt)


def test_build_prompt_requests_address_field():
    prompt = _build_prompt("Test")
    assert '"address": str' in prompt


def test_build_prompt_requests_material_and_labor_details():
    prompt = _build_prompt("Test")
    assert "Material- bzw. Arbeitsposition" in prompt
    assert "Menge, Einheit, Preis und ``worker_role``" in prompt
