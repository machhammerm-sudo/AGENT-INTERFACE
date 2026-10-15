"""P16 - Claude-Bildauswertung: letzter Ausweg, wenn lokal kein sicherer
Kandidat gefunden wurde. Wird NUR aufgerufen, wenn der Datenschutz-Schalter
des Objekts/Kunden das ausdruecklich erlaubt (siehe pipeline.py) - sonst
bleibt das Feld gelb/rot mit Vermerk. Schickt bewusst nur den betroffenen
Bildausschnitt, nicht das ganze Dokument."""

import base64
import io

from PIL import Image

from ..anthropic_client import get_client
from ..config import CHAT_MODEL
from .field_extraction import FieldCandidate, FieldSpec


def escalate_field(spec: FieldSpec, crop: Image.Image) -> FieldCandidate | None:
    buffer = io.BytesIO()
    crop.save(buffer, format="PNG")
    image_b64 = base64.b64encode(buffer.getvalue()).decode("ascii")

    prompt = (
        f"Das ist ein Ausschnitt aus dem Titelblock eines Bauplans. "
        f"Lies den Wert fuer das Feld '{spec.label}' ab "
        f"(moegliche Beschriftungen dafuer: {', '.join(spec.synonyms)}). "
        "Antworte NUR mit dem reinen Wert, ohne Beschriftung, ohne Erklaerung. "
        "Falls das Feld in diesem Ausschnitt nicht erkennbar ist, antworte exakt mit: UNBEKANNT"
    )

    try:
        client = get_client()
        response = client.messages.create(
            model=CHAT_MODEL,
            max_tokens=200,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/png", "data": image_b64},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        text = "".join(b.text for b in response.content if b.type == "text").strip()
    except Exception:
        return None

    if not text or text.upper() == "UNBEKANNT":
        return None

    return FieldCandidate(
        value=text,
        assignment_confidence=0.6,  # Cloud-Fallback: brauchbar, aber kein Ersatz fuer menschliche Pruefung
        ocr_confidence=0.0,  # keine OCR-Lesesicherheit, da nicht lokal gelesen
        match_type="escalation",
        label_score=0.0,
        rel_bbox=(0.0, 0.0, 1.0, 1.0),
    )
