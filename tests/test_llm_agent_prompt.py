import re

from app.llm_agent import _build_prompt


def test_build_prompt_preserves_quotes():
    transcript = 'Er sagte "Hallo" und "Tschüss"'
    prompt = _build_prompt(transcript)
    assert transcript in prompt
    # Ensure there are no extraneous surrounding quotes around transcript
    # preceding and following context should match expected format
    assert re.search(r"Text:\nEr sagte \"Hallo\" und \"Tschüss\"\n", prompt)
