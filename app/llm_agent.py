from openai import OpenAI
import requests
from app.settings import settings


def extract_invoice_context(transcript: str) -> str:
    prompt = f"""
Du bist ein KI-Assistent für Handwerker. Extrahiere aus folgendem Text eine strukturierte JSON-Rechnung gemäß folgendem Schema:

{{
  "type": "InvoiceContext",
  "customer": {{ "name": str }},
  "service": {{ "description": str, "materialIncluded": bool }},
  "amount": {{ "total": float, "currency": "EUR" }}
}}

Text: "{transcript}"
Nur JSON antworten.
"""
    if settings.llm_provider == "openai":
        client = OpenAI()
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": "Du bist ein strukturierter JSON-Extraktor für Handwerker."},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content
    elif settings.llm_provider == "ollama":
        url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
        resp = requests.post(
            url,
            json={"model": settings.llm_model, "prompt": prompt, "stream": False},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER {settings.llm_provider}")

