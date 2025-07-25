def extract_invoice_context(transcript: str) -> str:
    from openai import OpenAI
    client = OpenAI()
    prompt = f"""
    Du bist ein KI-Assistent für Handwerker. Extrahiere aus folgendem Text eine strukturierte JSON-Rechnung gemäß folgendem Schema:

    {{
      "type": "InvoiceContext",
      "customer": {{ "name": str }},
      "service": {{ "description": str, "materialIncluded": bool }},
      "amount": {{ "total": float, "currency": "EUR" }}
    }}

    Text: """{transcript}"""
    Nur JSON antworten.
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Du bist ein strukturierter JSON-Extraktor für Handwerker."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content