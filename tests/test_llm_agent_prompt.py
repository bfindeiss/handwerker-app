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


def test_build_prompt_requests_expected_keys():
    prompt = _build_prompt("Test", PreextractCandidates())
    assert "material_positions" in prompt
    assert "labor_hours" in prompt
    assert "trip_km" in prompt


def test_build_prompt_lists_candidates_before_text():
    prompt = _build_prompt("Test", PreextractCandidates())
    assert prompt.index("Kandidaten (JSON):") < prompt.index("Text:\n")
