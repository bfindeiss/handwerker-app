import re

from app.llm_agent import _build_prompt
from app.models import PreextractCandidates


def test_build_prompt_preserves_quotes():
    transcript = 'Er sagte "Hallo" und "Tschüss"'
    prompt = _build_prompt(transcript, PreextractCandidates())
    assert transcript in prompt
    # Ensure there are no extraneous surrounding quotes around transcript
    # preceding and following context should match expected format
    assert re.search(r"Text:\nEr sagte \"Hallo\" und \"Tschüss\"\n", prompt)


def test_build_prompt_requests_address_field():
    prompt = _build_prompt("Test", PreextractCandidates())
    assert '"address"' in prompt


def test_build_prompt_requests_material_and_labor_details():
    prompt = _build_prompt("Test", PreextractCandidates())
    assert '"line_items"' in prompt
    assert '"unit_price_cents"' in prompt
    assert '"material"' in prompt
    assert '"labor"' in prompt
    assert '"meister"' in prompt
    assert "Kandidaten (JSON):" in prompt
