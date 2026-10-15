"""Pruefstand: misst die Erkennungsguete an synthetischen Testplaenen.

Wichtiger als die reine Trefferquote ist der Anteil FALSCH-gruener Felder -
der soll nahe Null sein. Ergebnis wird mit Datum in der lokalen Datenbank
abgelegt, damit der Fortschritt ueber die Zeit sichtbar wird.

Aufruf: python -m app.documents.testbench.run_benchmark
"""

import json
from collections import defaultdict
from pathlib import Path

from PIL import Image
from rapidfuzz import fuzz

from ..field_extraction import FieldSpec, extract_fields
from ..region_detection import detect_rotation, find_titleblock_candidates, _rotate
from ..seed import DEFAULT_FIELDS

PLANS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "testdata" / "titleblocks"
MATCH_THRESHOLD = 90  # Fuzzy-Score, ab dem ein erkannter Wert als "richtig" gilt


def _field_specs() -> list[FieldSpec]:
    return [
        FieldSpec(field_key=d["field_key"], label=d["label"], synonyms=d["synonyms"], format_regex=d["format_regex"])
        for d in DEFAULT_FIELDS
    ]


def _values_match(value: str | None, expected: str | None) -> bool:
    if value is None or expected is None:
        return False
    norm_a = " ".join(value.lower().split())
    norm_b = " ".join(expected.lower().split())
    return fuzz.ratio(norm_a, norm_b) >= MATCH_THRESHOLD


def run_benchmark(plans_dir: Path = PLANS_DIR) -> dict:
    solutions_path = plans_dir / "loesungen.json"
    if not solutions_path.exists():
        raise FileNotFoundError(
            f"Keine Loesungsdatei gefunden unter {solutions_path} - erst "
            "generate_synthetic_plans ausfuehren."
        )
    solutions = json.loads(solutions_path.read_text(encoding="utf-8"))
    field_specs = _field_specs()
    all_synonyms = [s for spec in field_specs for s in spec.synonyms]

    per_field = defaultdict(lambda: {"hits": 0, "total": 0, "green": 0, "false_green": 0, "no_result": 0})
    per_template = defaultdict(lambda: {"hits": 0, "total": 0, "green": 0, "false_green": 0, "no_result": 0})
    overall = {"hits": 0, "total": 0, "green": 0, "false_green": 0, "no_result": 0}

    for filename, meta in solutions.items():
        template_id = meta["template_id"]
        ground_truth = meta["fields"]

        image = Image.open(plans_dir / filename).convert("RGB")
        rotation = detect_rotation(image)
        upright = _rotate(image, rotation)

        candidates = find_titleblock_candidates(upright, all_synonyms)
        chosen = candidates[0]
        w, h = upright.size
        box = (
            int(chosen.rel_x * w), int(chosen.rel_y * h),
            int((chosen.rel_x + chosen.rel_w) * w), int((chosen.rel_y + chosen.rel_h) * h),
        )
        crop = upright.crop(box)

        results = extract_fields(crop, field_specs)

        for result in results:
            expected = ground_truth.get(result.field_key)
            chosen_value = result.candidates[0].value if result.candidates else None

            if expected is None:
                correct = result.status == "red"
            else:
                correct = result.status != "red" and _values_match(chosen_value, expected)

            for bucket in (per_field[result.field_key], per_template[template_id], overall):
                bucket["total"] += 1
                bucket["hits"] += int(correct)
                if result.status == "green":
                    bucket["green"] += 1
                    if not correct:
                        bucket["false_green"] += 1
                if result.status == "red":
                    bucket["no_result"] += 1

    def _rates(bucket):
        total = bucket["total"] or 1
        green = bucket["green"] or 1
        return {
            "hit_rate": round(bucket["hits"] / total, 4),
            "false_green_rate": round(bucket["false_green"] / green, 4) if bucket["green"] else 0.0,
            "no_result_rate": round(bucket["no_result"] / total, 4),
            "n": bucket["total"],
        }

    return {
        "overall": _rates(overall),
        "per_field": {k: _rates(v) for k, v in per_field.items()},
        "per_template": {k: _rates(v) for k, v in per_template.items()},
        "plan_count": len(solutions),
    }


def _print_summary(result: dict) -> None:
    o = result["overall"]
    print(f"Testplaene: {result['plan_count']}")
    print(f"Trefferquote gesamt:        {o['hit_rate']*100:.1f}%")
    print(f"Falsch-gruen-Quote:         {o['false_green_rate']*100:.1f}%  (Ziel: nahe 0)")
    print(f"Anteil ohne Ergebnis (rot): {o['no_result_rate']*100:.1f}%")
    print()
    print("Je Feld:")
    for key, r in sorted(result["per_field"].items()):
        print(f"  {key:24s} Treffer {r['hit_rate']*100:5.1f}%  falsch-gruen {r['false_green_rate']*100:5.1f}%  (n={r['n']})")
    print()
    print("Je Titelblock-Vorlage:")
    for key, r in sorted(result["per_template"].items()):
        print(f"  {key:16s} Treffer {r['hit_rate']*100:5.1f}%  falsch-gruen {r['false_green_rate']*100:5.1f}%  (n={r['n']})")


def store_run(result: dict) -> None:
    """Speichert das Ergebnis mit Datum in der Nauteron-Datenbank, damit der
    Fortschritt ueber die Zeit sichtbar bleibt."""
    from ...database import Base, SessionLocal, engine
    from ..models import BenchmarkRun

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.add(
            BenchmarkRun(
                overall_hit_rate=result["overall"]["hit_rate"],
                false_green_rate=result["overall"]["false_green_rate"],
                no_result_rate=result["overall"]["no_result_rate"],
                per_field_json=json.dumps(result["per_field"], ensure_ascii=False),
                per_template_json=json.dumps(result["per_template"], ensure_ascii=False),
                plan_count=result["plan_count"],
            )
        )
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    res = run_benchmark()
    _print_summary(res)
    store_run(res)
    print("\nErgebnis in der Datenbank gespeichert (BenchmarkRun).")
