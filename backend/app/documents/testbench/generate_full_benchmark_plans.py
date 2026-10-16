"""P28 - erweiterter Pruefstand: erzeugt >=30 synthetische Testplaene fuer
eine ehrliche Abnahme-Messung. Mehrere "Objekte" (Bauvorhaben) mit jeweils
mehreren Planblaettern, verschiedene Layouts und Schriftarten, und gezielt
eingebaute Fehlerfaelle (siehe ERROR_TYPES unten).

Aufruf: python -m app.documents.testbench.generate_full_benchmark_plans

Alle Werte sind frei erfunden, keine echten Namen oder Daten.
"""

import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "testdata" / "titleblocks_full"
FONTS_DIR = Path(__file__).resolve().parent / "fonts"
PAGE_SIZE = (1600, 1131)

FONT_FILES = {
    "dejavu": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "serif": "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "freesans": "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "inter": "/usr/share/fonts/opentype/inter/Inter-Regular.otf",
}
HANDWRITING_FONT = str(FONTS_DIR / "Caveat.ttf")

RNG = random.Random(20261016)  # fester Seed -> reproduzierbare Testplaene


def _font(name: str, size: int):
    return ImageFont.truetype(FONT_FILES[name], size)


def _new_page():
    img = Image.new("RGB", PAGE_SIZE, "white")
    return img, ImageDraw.Draw(img)


LABEL_TEXT = {
    "bauherr": "Bauherr", "planverfasser": "Planverfasser", "bauvorhaben": "Bauvorhaben",
    "grundstuecksadresse": "Adresse", "gemeinde": "Gemeinde", "flurstueck": "Flurstueck",
    "massstab": "Massstab", "plannummer": "Plannummer", "planinhalt": "Planinhalt",
    "datum": "Datum", "index": "Index", "flaeche": "Flaeche",
}
ALT_LABEL_TEXT = {
    "bauherr": "Auftraggeber", "planverfasser": "Verfasser", "bauvorhaben": "Vorhaben",
    "gemeinde": "Ort", "massstab": "M.", "datum": "Stand", "plannummer": "Plan-Nr.",
}

# ---------- Objekte (Bauvorhaben) mit je mehreren Planblaettern ----------

OBJECTS = [
    {
        "object_id": "OBJ-A",
        "bauherr": "Petra Gruber", "planverfasser": "Architekturbuero Sued",
        "bauvorhaben": "Anbau Garage", "grundstuecksadresse": "Lindenweg 7",
        "gemeinde": "Seehausen", "flurstueck": "118/2",
    },
    {
        "object_id": "OBJ-B",
        "bauherr": "Thomas Berger", "planverfasser": "Buero Hoch Drei",
        "bauvorhaben": "Neubau Doppelhaus", "grundstuecksadresse": "Birkenallee 4",
        "gemeinde": "Waldkirch", "flurstueck": "340",
    },
    {
        "object_id": "OBJ-C",
        "bauherr": "Nina Keller", "planverfasser": "Planwerk Keller und Partner",
        "bauvorhaben": "Dachgeschossausbau", "grundstuecksadresse": "Rosenstrasse 19",
        "gemeinde": "Bergstetten", "flurstueck": "76/5",
    },
    {
        "object_id": "OBJ-D",
        "bauherr": "Stefan Wolf", "planverfasser": "Architekturbuero Nord",
        "bauvorhaben": "Neubau Einfamilienhaus", "grundstuecksadresse": "Musterweg 12",
        "gemeinde": "Musterstadt", "flurstueck": "245/3",
    },
]

SHEET_CONTENTS = ["Lageplan", "Grundriss EG", "Grundriss OG", "Schnitt A-A", "Ansicht Nord", "Ansicht Sued"]
DATES = ["04.02.2026", "11.02.2026", "18.02.2026", "25.02.2026"]
SCALES = ["1:100", "1:50", "1:200"]
INDEXES = ["A", "B", "C"]

LAYOUTS = ["bottom_right", "right_strip", "top", "rotated90", "rotated180", "rotated270", "no_frame"]
FONT_CYCLE = ["dejavu", "serif", "freesans", "inter"]


FIELD_ORDER = ["bauherr", "planverfasser", "bauvorhaben", "grundstuecksadresse", "gemeinde", "flurstueck", "massstab", "datum", "plannummer", "index"]


def _render_titleblock(img, draw, layout, fields_dict, font_name, handwriting_field=None, alt_labels=False):
    labels = ALT_LABEL_TEXT if alt_labels else LABEL_TEXT
    order = [k for k in FIELD_ORDER if k in fields_dict]
    font = _font(font_name, 17)

    def value_font(field_key):
        if handwriting_field and field_key == handwriting_field:
            return ImageFont.truetype(HANDWRITING_FONT, 26)
        return font

    # fuer handschriftliche Werte brauchen wir individuelles Font-Handling je Zelle
    if layout in ("bottom_right", "rotated90", "rotated180", "rotated270"):
        box = (PAGE_SIZE[0] - 560, PAGE_SIZE[1] - 360, PAGE_SIZE[0] - 20, PAGE_SIZE[1] - 20)
        _draw_two_col_custom(draw, box, order, fields_dict, labels, font, value_font)
        drawn_keys = order
    elif layout == "right_strip":
        box = (PAGE_SIZE[0] - 300, 20, PAGE_SIZE[0] - 20, PAGE_SIZE[1] - 20)
        _draw_stacked_custom(draw, box, order, fields_dict, labels, _font(font_name, 15), value_font)
        drawn_keys = order
    elif layout == "top":
        box = (20, 20, PAGE_SIZE[0] - 20, 160)
        top_order = order[:4]
        _draw_top_custom(draw, box, top_order, fields_dict, labels, font, value_font)
        drawn_keys = top_order
    elif layout == "no_frame":
        _draw_no_frame_custom(draw, (120, 120), order, fields_dict, labels, font, value_font)
        drawn_keys = order
    else:
        box = (PAGE_SIZE[0] - 560, PAGE_SIZE[1] - 360, PAGE_SIZE[0] - 20, PAGE_SIZE[1] - 20)
        _draw_two_col_custom(draw, box, order, fields_dict, labels, font, value_font)
        drawn_keys = order

    return drawn_keys


def _draw_two_col_custom(draw, box, order, fields_dict, labels, label_font, value_font_fn):
    x0, y0, x1, y1 = box
    n = len(order)
    draw.rectangle(box, outline="black", width=2)
    row_h = (y1 - y0) / n
    col_x = x0 + (x1 - x0) * 0.33
    for i, key in enumerate(order):
        ry = y0 + i * row_h
        if i > 0:
            draw.line([x0, ry, x1, ry], fill="black", width=1)
        draw.text((x0 + 8, ry + 6), labels.get(key, LABEL_TEXT[key]), font=label_font, fill="black")
        value = fields_dict.get(key)
        if value is not None:
            draw.text((col_x + 8, ry + 2), value, font=value_font_fn(key), fill="black")
    draw.line([col_x, y0, col_x, y1], fill="black", width=1)


def _draw_stacked_custom(draw, box, order, fields_dict, labels, label_font, value_font_fn):
    x0, y0, x1, y1 = box
    n = len(order)
    draw.rectangle(box, outline="black", width=2)
    row_h = (y1 - y0) / n
    for i, key in enumerate(order):
        ry = y0 + i * row_h
        if i > 0:
            draw.line([x0, ry, x1, ry], fill="black", width=1)
        draw.text((x0 + 6, ry + 4), labels.get(key, LABEL_TEXT[key]), font=label_font, fill="black")
        value = fields_dict.get(key)
        if value is not None:
            draw.text((x0 + 6, ry + 4 + row_h * 0.45), value, font=value_font_fn(key), fill="black")


def _draw_top_custom(draw, box, order, fields_dict, labels, label_font, value_font_fn):
    x0, y0, x1, y1 = box
    draw.rectangle(box, outline="black", width=2)
    col_w = (x1 - x0) / len(order)
    for i, key in enumerate(order):
        cx = x0 + i * col_w
        if i > 0:
            draw.line([cx, y0, cx, y1], fill="black", width=1)
        draw.text((cx + 8, y0 + 8), labels.get(key, LABEL_TEXT[key]), font=label_font, fill="black")
        value = fields_dict.get(key)
        if value is not None:
            draw.text((cx + 8, y0 + 70), value, font=value_font_fn(key), fill="black")


def _draw_no_frame_custom(draw, origin, order, fields_dict, labels, label_font, value_font_fn):
    x0, y0 = origin
    y = y0
    for key in order:
        draw.text((x0, y), f"{labels.get(key, LABEL_TEXT[key])}:", font=label_font, fill="black")
        value = fields_dict.get(key)
        if value is not None:
            draw.text((x0 + 190, y), value, font=value_font_fn(key), fill="black")
        y += 38


def _add_decoy_text(draw, with_date=True):
    """Platziert einen Freigabevermerk mit einem eigenen Datum weitab vom
    Titelblock, um zu pruefen, ob er faelschlich als Feldwert uebernommen
    wird oder die Bereichs-Erkennung in die Irre fuehrt."""
    font = _font("dejavu", 15)
    draw.rectangle([60, 55, 340, 150], outline="black", width=1)
    draw.text((70, 65), "Eingangsvermerk Bauaufsicht", font=font, fill="black")
    if with_date:
        draw.text((70, 95), "Datum", font=font, fill="black")
        draw.text((70, 118), "03.01.2026", font=font, fill="black")
    draw.ellipse([400, 450, 540, 590], outline="black", width=2)
    draw.text((420, 510), "EINGEGANGEN", font=_font("dejavu", 13), fill="black")


def _apply_rotation(img, layout):
    if layout == "rotated90":
        return img.rotate(-90, expand=True)
    if layout == "rotated180":
        return img.rotate(180, expand=True)
    if layout == "rotated270":
        return img.rotate(90, expand=True)
    return img


def _ground_truth_fields(fields_dict, order, omit=None):
    omit = omit or set()
    return {k: v for k, v in fields_dict.items() if k in order and k not in omit and v is not None}


def generate_all() -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    solutions = {}
    sheet_counter = 0
    error_count = 0
    total_count = 0

    plan_specs = []  # (object, sheet_index, layout, font_name, error_type)

    for obj_idx, obj in enumerate(OBJECTS):
        n_sheets = 8 if obj_idx < 2 else 7  # ergibt in Summe >30 Blaetter
        for sheet_idx in range(n_sheets):
            layout = LAYOUTS[sheet_counter % len(LAYOUTS)]
            font_name = FONT_CYCLE[sheet_counter % len(FONT_CYCLE)]
            plan_specs.append([obj, sheet_idx, layout, font_name, None])
            sheet_counter += 1

    # ---- gezielte Fehlerfaelle auf einzelne Blaetter verteilen ----
    error_assignments = {
        0: "inconsistent_flurstueck",
        3: "missing_date",
        6: "impossible_scale",
        9: "handwriting_value",
        12: "decoy_text",
        15: "alt_labels_and_font",
        18: "no_frame_noisy",
        21: "degraded_scan",
        24: "inconsistent_flurstueck",
        27: "missing_date",
        28: "decoy_text",
    }
    for idx, err in error_assignments.items():
        if idx < len(plan_specs):
            plan_specs[idx][4] = err
            error_count += 1

    for i, (obj, sheet_idx, layout, font_name, error_type) in enumerate(plan_specs):
        fields = dict(obj)
        object_id = fields.pop("object_id")
        fields["plannummer"] = f"{object_id}-{sheet_idx + 1:02d}"
        fields["planinhalt"] = SHEET_CONTENTS[sheet_idx % len(SHEET_CONTENTS)]
        fields["datum"] = DATES[sheet_idx % len(DATES)]
        fields["massstab"] = SCALES[sheet_idx % len(SCALES)]
        fields["index"] = INDEXES[sheet_idx % len(INDEXES)]

        omit_from_truth = set()
        alt_labels = False
        handwriting_field = None
        notes = ""

        if error_type == "inconsistent_flurstueck":
            fields["flurstueck"] = fields["flurstueck"] + "X"  # weicht bewusst vom Objekt ab
            notes = "Flurstueck weicht von den anderen Blaettern desselben Objekts ab (absichtlich)."
        elif error_type == "missing_date":
            fields["datum"] = None
            omit_from_truth.add("datum")
            notes = "Plandatum fehlt auf dem Blatt (absichtlich)."
        elif error_type == "impossible_scale":
            fields["massstab"] = "1:0"
            notes = "Unmoeglicher Massstab 1:0 (absichtlich) - testet, ob das System Werte ungeprueft uebernimmt."
        elif error_type == "handwriting_value":
            handwriting_field = "bauherr"
            notes = "Bauherr-Wert in handschriftlich wirkender Schrift (Caveat) gerendert."
        elif error_type == "decoy_text":
            notes = "Taeuschend aehnliches Datum ausserhalb des Titelblocks platziert."
        elif error_type == "alt_labels_and_font":
            alt_labels = True
            notes = "Alternative Beschriftungen (z.B. 'Auftraggeber' statt 'Bauherr')."
        elif error_type == "no_frame_noisy":
            layout = "no_frame"
            notes = "Kein Rahmen, zusaetzlich Stoertext auf der Seite."
        elif error_type == "degraded_scan":
            notes = "Simulierte Scan-Qualitaet: Schiefstand + Weichzeichnung."

        img, draw = _new_page()
        # Die Seitenumrandung wird immer gezeichnet (simuliert den
        # Blattrand) - "no_frame" bezieht sich nur auf das Fehlen von
        # Rahmen/Raster UM DEN TITELBLOCK selbst, das eigentliche Testziel.
        draw.rectangle([20, 20, PAGE_SIZE[0] - 20, PAGE_SIZE[1] - 20], outline="black", width=2)

        drawn_keys = _render_titleblock(img, draw, layout, fields, font_name, handwriting_field, alt_labels)

        if error_type == "decoy_text":
            _add_decoy_text(draw, with_date=True)
        if error_type == "no_frame_noisy":
            _add_decoy_text(draw, with_date=False)

        img = _apply_rotation(img, layout)

        if error_type == "degraded_scan":
            img = img.rotate(2.0, expand=True, fillcolor="white")
            img = img.filter(ImageFilter.GaussianBlur(radius=1.0))

        template_id = f"{object_id}_{layout}_{font_name}"
        filename = f"{object_id.lower()}_sheet{sheet_idx + 1:02d}_{layout}.png"
        img.save(OUT_DIR / filename)

        truth_fields = _ground_truth_fields(fields, drawn_keys, omit_from_truth)

        solutions[filename] = {
            "template_id": template_id,
            "layout_type": layout,
            "object_id": object_id,
            "error_type": error_type,
            "notes": notes,
            "fields": truth_fields,
        }
        total_count += 1

    # ---- doppelt vorhandener Plan: eine bestehende, fehlerfreie Datei real duplizieren ----
    clean_items = [fn for fn, meta in solutions.items() if meta["error_type"] is None]
    if clean_items:
        source_filename = clean_items[0]
        duplicate_filename = "duplicate_of_" + source_filename
        (OUT_DIR / duplicate_filename).write_bytes((OUT_DIR / source_filename).read_bytes())
        dup_meta = dict(solutions[source_filename])
        dup_meta["error_type"] = "duplicate_plan"
        dup_meta["notes"] = f"Exakte Kopie von {source_filename} (absichtlich)."
        solutions[duplicate_filename] = dup_meta
        total_count += 1
        error_count += 1

    # ---- dev/acceptance-Split: jedes dritte Blatt in die Abnahme-Gruppe -
    # getrennt fuer fehlerfreie und fehlerhafte Blaetter, damit die
    # Abnahme-Gruppe nicht zufaellig fast nur "einfache" Plaene bekommt.
    clean_sorted = sorted(fn for fn, m in solutions.items() if m["error_type"] is None)
    error_sorted = sorted(fn for fn, m in solutions.items() if m["error_type"] is not None)
    for group in (clean_sorted, error_sorted):
        for i, fn in enumerate(group):
            solutions[fn]["split"] = "acceptance" if i % 3 == 2 else "dev"

    with (OUT_DIR / "loesungen.json").open("w", encoding="utf-8") as f:
        json.dump(solutions, f, ensure_ascii=False, indent=2)

    dev_n = sum(1 for m in solutions.values() if m["split"] == "dev")
    acc_n = sum(1 for m in solutions.values() if m["split"] == "acceptance")
    err_n = sum(1 for m in solutions.values() if m["error_type"] is not None)

    print(f"{total_count} Testplaene erzeugt in {OUT_DIR}")
    print(f"  davon dev={dev_n}, acceptance={acc_n}, mit Fehlerfall={err_n} ({err_n/total_count*100:.0f}%)")
    return solutions


if __name__ == "__main__":
    generate_all()
