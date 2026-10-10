"""Kapselt jede Kommunikation mit der Anthropic-API an einer Stelle.

Zwei Modelle kommen zum Einsatz:
- CHAT_MODEL: fuer die eigentlichen Gespraeche mit einem Agenten (faehig, aber teurer).
- CLASSIFY_MODEL: fuer die guenstige automatische Kategorie-Zuordnung im Hintergrund.
"""

import json
from typing import Optional

from anthropic import Anthropic

from .config import ANTHROPIC_API_KEY, CHAT_MODEL, CLASSIFY_MODEL
from .models import Agent, Category

_client: Optional[Anthropic] = None


def get_client() -> Anthropic:
    global _client
    if _client is None:
        if not ANTHROPIC_API_KEY:
            raise RuntimeError(
                "Kein ANTHROPIC_API_KEY gesetzt. Bitte backend/.env anlegen "
                "(siehe backend/.env.example)."
            )
        _client = Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def build_system_prompt(agent: Agent) -> str:
    restriction_note = ""
    if agent.is_restricted:
        restriction_note = (
            "\n\nWICHTIG: Du bist eine ueberwachende, beratende Instanz. Du triffst "
            "selbst KEINE kritischen Sicherheits- oder sonstigen riskanten "
            "Entscheidungen autonom. Du erklaerst Risiken immer in einfacher, "
            "nicht-technischer Sprache mit einer klaren Einschaetzung (z.B. "
            "gering / mittel / hoch) und schlaegst Massnahmen vor, die der Nutzer "
            "erst ausdruecklich bestaetigen muss."
        )

    return (
        f"Du bist {agent.name}, ein spezialisierter KI-Agent im Team 'Nauteron' "
        f"mit dem Schwerpunkt '{agent.role_title}'.\n\n"
        f"Deine Kernaufgabe: {agent.core_task}\n\n"
        "Antworte klar, knapp und auf Deutsch. Dein Gespraechspartner ist kein "
        "Programmierer - vermeide unnoetigen Fachjargon. Wenn du etwas nicht "
        "sicher weisst oder eine Information aus der bisherigen Historie "
        "brauchst, sag das offen, statt zu spekulieren."
        + restriction_note
    )


def send_chat_message(agent: Agent, history: list[dict], user_message: str) -> str:
    """history: Liste von {'role': 'user'|'assistant', 'content': str}, nur die
    letzten paar Nachrichten dieses einen Agenten-Gespraechs (siehe config.py),
    NICHT die komplette gespeicherte Historie."""

    client = get_client()
    messages = history + [{"role": "user", "content": user_message}]

    response = client.messages.create(
        model=CHAT_MODEL,
        max_tokens=2048,
        system=build_system_prompt(agent),
        messages=messages,
    )
    return "".join(
        block.text for block in response.content if block.type == "text"
    )


def classify_category(text: str, categories: list[Category]) -> Optional[int]:
    """Guenstiger Hintergrund-Aufruf, der den uebergebenen Text einer der
    vorhandenen Kategorien zuordnet. Gibt die category.id zurueck oder None,
    wenn keine passt oder der Aufruf fehlschlaegt (Fehler werden bewusst nicht
    weitergeworfen - eine fehlende automatische Zuordnung ist kein kritischer
    Fehler, der Nutzer kann die Kategorie jederzeit manuell setzen)."""

    if not ANTHROPIC_API_KEY or not categories:
        return None

    options = "\n".join(f"{c.id}: {c.name} - {c.description}" for c in categories)
    prompt = (
        "Ordne den folgenden Text genau einer der folgenden Kategorien zu. "
        "Antworte ausschliesslich mit einem JSON-Objekt der Form "
        '{\"category_id\": <Zahl>} - sonst nichts.\n\n'
        f"Kategorien:\n{options}\n\nText:\n{text}"
    )

    try:
        client = get_client()
        response = client.messages.create(
            model=CLASSIFY_MODEL,
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(
            block.text for block in response.content if block.type == "text"
        )
        data = json.loads(raw)
        category_id = int(data["category_id"])
        valid_ids = {c.id for c in categories}
        return category_id if category_id in valid_ids else None
    except Exception:
        return None
