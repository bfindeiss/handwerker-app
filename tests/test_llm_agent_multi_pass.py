import json

from app import llm_agent


class DummyChatResponse:
    class DummyChoice:
        class DummyMessage:
            def __init__(self, content):
                self.content = content

        def __init__(self, content):
            self.message = DummyChatResponse.DummyChoice.DummyMessage(content)

    def __init__(self, content):
        self.choices = [DummyChatResponse.DummyChoice(content)]


class DummyOpenAI:
    def __init__(self, responses):
        self.responses = responses
        self.index = 0
        self.calls = 0

    class Chat:
        def __init__(self, parent):
            self.parent = parent

        class Completions:
            def __init__(self, parent):
                self.parent = parent

            def create(self, **kwargs):
                self.parent.parent.calls += 1
                if self.parent.parent.index < len(self.parent.parent.responses):
                    content = self.parent.parent.responses[self.parent.parent.index]
                    self.parent.parent.index += 1
                else:
                    content = self.parent.parent.responses[-1]
                return DummyChatResponse(content)

        @property
        def completions(self):
            return DummyOpenAI.Chat.Completions(self)

    @property
    def chat(self):
        return DummyOpenAI.Chat(self)


def test_multi_pass_repairs_invalid_json(monkeypatch):
    responses = [
        json.dumps(
            {
                "customer": {
                    "name": "Klara",
                    "address": {
                        "street": "Hauptstraße 5",
                        "postal_code": "12345",
                        "city": "Berlin",
                    },
                }
            }
        ),
        "not json",
        json.dumps(
            {
                "line_items": [
                    {
                        "description": "Tür",
                        "type": "material",
                        "quantity": 1.0,
                        "unit": "Stk",
                        "unit_price_cents": 12000,
                    }
                ]
            }
        ),
        json.dumps(
            {
                "line_items": [
                    {
                        "description": "Meisterstunden",
                        "type": "labor",
                        "role": "meister",
                        "quantity": 2.0,
                        "unit": "h",
                        "unit_price_cents": 8000,
                    },
                    {
                        "description": "Gesellenstunden",
                        "type": "labor",
                        "role": "geselle",
                        "quantity": 3.0,
                        "unit": "h",
                        "unit_price_cents": 5000,
                    },
                ]
            }
        ),
        json.dumps(
            {
                "line_items": [
                    {
                        "description": "Anfahrt",
                        "type": "travel",
                        "quantity": 35.0,
                        "unit": "km",
                        "unit_price_cents": 150,
                    }
                ]
            }
        ),
    ]
    dummy = DummyOpenAI(responses)
    monkeypatch.setattr(llm_agent.settings, "llm_provider", "openai")
    monkeypatch.setattr(llm_agent, "OpenAI", lambda: dummy)
    result = llm_agent.extract_invoice_context(
        "Tür und Fenster, Meister 2h, Geselle 3h, 35km Anfahrt"
    )
    payload = json.loads(result)
    assert payload["customer"]["name"] == "Klara"
    assert len(payload["line_items"]) == 4
    assert dummy.calls == 5
