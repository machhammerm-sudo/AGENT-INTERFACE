"""Erzeugt synthetische Test-Titelbloecke mit verschiedenen Layouts fuer den
Pruefstand. Rein lokal, keine echten Kundendaten - Werte sind frei erfunden.

Aufruf: python -m app.documents.testbench.generate_synthetic_plans
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "testdata" / "titleblocks"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
PAGE_SIZE = (1600, 1131)  # A4 quer bei ~150dpi


def _font(size=18):
    return ImageFont.truetype(FONT_PATH, size)


def _new_page():
    img = Image.new("RGB", PAGE_SIZE, "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, PAGE_SIZE[0] - 20, PAGE_SIZE[1] - 20], outline="black", width=3)
    return img, draw


def _draw_two_col_block(draw, box, pairs, font):
    """box=(x0,y0,x1,y1); pairs=[(label,value), ...] - klassisches
    zweispaltiges Titelblock-Raster."""
    x0, y0, x1, y1 = box
    n = len(pairs)
    draw.rectangle(box, outline="black", width=2)
    row_h = (y1 - y0) / n
    col_x = x0 + (x1 - x0) * 0.33
    for i, (label, value) in enumerate(pairs):
        ry = y0 + i * row_h
        if i > 0:
            draw.line([x0, ry, x1, ry], fill="black", width=1)
        draw.text((x0 + 8, ry + 6), label, font=font, fill="black")
        draw.text((col_x + 8, ry + 6), value, font=font, fill="black")
    draw.line([col_x, y0, col_x, y1], fill="black", width=1)


def _draw_stacked_block(draw, box, pairs, font):
    """box=(x0,y0,x1,y1); pairs=[(label,value), ...] - Label ueber Wert,
    typisch fuer einen schmalen Rand-Streifen."""
    x0, y0, x1, y1 = box
    n = len(pairs)
    draw.rectangle(box, outline="black", width=2)
    row_h = (y1 - y0) / n
    for i, (label, value) in enumerate(pairs):
        ry = y0 + i * row_h
        if i > 0:
            draw.line([x0, ry, x1, ry], fill="black", width=1)
        draw.text((x0 + 6, ry + 4), label, font=font, fill="black")
        draw.text((x0 + 6, ry + 4 + row_h * 0.45), value, font=font, fill="black")


FIELD_VALUES = {
    "bauherr": "Max Mustermann",
    "planverfasser": "Architekturbuero Nord",
    "bauvorhaben": "Neubau EFH",
    "grundstuecksadresse": "Musterweg 12",
    "gemeinde": "Musterstadt",
    "flurstueck": "245/3",
    "massstab": "1:100",
    "plannummer": "A-104",
    "planinhalt": "Grundriss EG",
    "datum": "12.03.2026",
    "index": "B",
    "flaeche": "512 m2",
}

LABEL_TEXT = {
    "bauherr": "Bauherr",
    "planverfasser": "Planverfasser",
    "bauvorhaben": "Bauvorhaben",
    "grundstuecksadresse": "Adresse",
    "gemeinde": "Gemeinde",
    "flurstueck": "Flurstueck",
    "massstab": "Massstab",
    "plannummer": "Plannummer",
    "planinhalt": "Planinhalt",
    "datum": "Datum",
    "index": "Index",
    "flaeche": "Flaeche",
}

ALT_LABEL_TEXT = {
    "bauherr": "Auftraggeber",
    "planverfasser": "Verfasser",
    "bauvorhaben": "Vorhaben",
    "gemeinde": "Ort",
    "massstab": "M.",
    "datum": "Stand",
    "plannummer": "Plan-Nr.",
}


def _pairs(fields, labels=LABEL_TEXT):
    return [(labels.get(f, LABEL_TEXT[f]), FIELD_VALUES[f]) for f in fields]


def plan_bottom_right():
    img, draw = _new_page()
    fields = ["bauherr", "bauvorhaben", "massstab", "datum", "plannummer", "gemeinde"]
    box = (PAGE_SIZE[0] - 520, PAGE_SIZE[1] - 320, PAGE_SIZE[0] - 20, PAGE_SIZE[1] - 20)
    _draw_two_col_block(draw, box, _pairs(fields), _font())
    return img, {f: FIELD_VALUES[f] for f in fields}, "bottom_right"


def plan_right_strip():
    img, draw = _new_page()
    fields = ["bauherr", "planverfasser", "bauvorhaben", "massstab", "datum", "plannummer", "index"]
    box = (PAGE_SIZE[0] - 280, 20, PAGE_SIZE[0] - 20, PAGE_SIZE[1] - 20)
    _draw_stacked_block(draw, box, _pairs(fields), _font(16))
    return img, {f: FIELD_VALUES[f] for f in fields}, "right_strip"


def plan_top():
    img, draw = _new_page()
    fields = ["bauherr", "bauvorhaben", "gemeinde", "datum"]
    box = (20, 20, PAGE_SIZE[0] - 20, 160)
    # vierspaltig statt zweispaltig
    x0, y0, x1, y1 = box
    draw.rectangle(box, outline="black", width=2)
    col_w = (x1 - x0) / len(fields)
    font = _font()
    for i, f in enumerate(fields):
        cx = x0 + i * col_w
        if i > 0:
            draw.line([cx, y0, cx, y1], fill="black", width=1)
        draw.text((cx + 8, y0 + 8), LABEL_TEXT[f], font=font, fill="black")
        draw.text((cx + 8, y0 + 70), FIELD_VALUES[f], font=font, fill="black")
    return img, {f: FIELD_VALUES[f] for f in fields}, "top"


def plan_rotated():
    img, truth, _ = plan_bottom_right()
    rotated = img.rotate(-90, expand=True)
    return rotated, truth, "rotated"


def plan_noisy_stamps():
    img, draw = _new_page()
    fields = ["bauherr", "bauvorhaben", "massstab", "datum", "plannummer", "gemeinde"]
    box = (PAGE_SIZE[0] - 520, PAGE_SIZE[1] - 320, PAGE_SIZE[0] - 20, PAGE_SIZE[1] - 20)
    _draw_two_col_block(draw, box, _pairs(fields), _font())

    small = _font(14)
    draw.text((60, 60), "Freigabevermerk Bauaufsicht", font=small, fill="black")
    draw.text((60, 85), "nicht rechtsverbindlich", font=small, fill="black")
    draw.ellipse([700, 450, 850, 600], outline="black", width=2)
    draw.text((715, 510), "GEPRUEFT", font=small, fill="black")
    draw.text((900, 150), "Revision A - vorlaeufig", font=small, fill="black")
    return img, {f: FIELD_VALUES[f] for f in fields}, "noisy_stamps"


def plan_alt_labels():
    img, draw = _new_page()
    fields = ["bauherr", "planverfasser", "bauvorhaben", "gemeinde", "massstab", "datum", "plannummer"]
    box = (PAGE_SIZE[0] - 560, PAGE_SIZE[1] - 360, PAGE_SIZE[0] - 20, PAGE_SIZE[1] - 20)
    _draw_two_col_block(draw, box, _pairs(fields, ALT_LABEL_TEXT), _font())
    return img, {f: FIELD_VALUES[f] for f in fields}, "alt_labels"


def plan_with_errors():
    img, draw = _new_page()
    fields = ["bauherr", "bauvorhaben", "massstab", "datum", "plannummer", "gemeinde"]
    box = (PAGE_SIZE[0] - 520, PAGE_SIZE[1] - 320, PAGE_SIZE[0] - 20, PAGE_SIZE[1] - 20)
    _draw_two_col_block(draw, box, _pairs(fields), _font())
    # Scan-Qualitaet simulieren: leichter Schiefstand + Weichzeichnung + Rauschen
    degraded = img.rotate(2.2, expand=True, fillcolor="white")
    degraded = degraded.filter(ImageFilter.GaussianBlur(radius=1.1))
    return degraded, {f: FIELD_VALUES[f] for f in fields}, "with_errors"


GENERATORS = [
    plan_bottom_right,
    plan_right_strip,
    plan_top,
    plan_rotated,
    plan_noisy_stamps,
    plan_alt_labels,
    plan_with_errors,
]


def generate_all() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    solutions = {}
    for gen in GENERATORS:
        img, ground_truth, template_id = gen()
        filename = f"{template_id}.png"
        img.save(OUT_DIR / filename)
        solutions[filename] = {"template_id": template_id, "fields": ground_truth}

    with (OUT_DIR / "loesungen.json").open("w", encoding="utf-8") as f:
        json.dump(solutions, f, ensure_ascii=False, indent=2)

    print(f"{len(solutions)} Testplaene erzeugt in {OUT_DIR}")


if __name__ == "__main__":
    generate_all()
