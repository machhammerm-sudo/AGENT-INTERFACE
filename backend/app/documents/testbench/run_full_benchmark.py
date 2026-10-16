"""P28 - erweiterter Pruefstand / Abnahme-Messung.

Schickt alle synthetischen Testplaene durch GENAU DIE SELBE Pipeline wie
echte Uploads (pipeline.process_document) - keine Testsonderwege, keine
Cloud-Aufrufe (die Datenschutz-Schalter bleiben unberuehrt auf Standard
"aus"). Laeuft gegen eine isolierte, wegwerfbare Test-Datenbank, damit keine
synthetischen Testkunden in der echten Nauteron-Datenbank landen. Nur die
Zusammenfassung (Kennzahlen + Pfade zum Bericht) wird am Ende in die echte
Datenbank geschrieben, damit der Fortschritt ueber mehrere Laeufe sichtbar
bleibt.

Aufruf: python -m app.documents.testbench.run_full_benchmark
"""

import json
import random
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from rapidfuzz import fuzz
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ...database import Base as AppBase
from ..metrics import maybe_sample_green_field
from ..models import (
    Customer,
    DocumentFieldResult,
    DocumentRegion,
    GreenSampleCheck,
    TitleblockDocument,
)
from ..pipeline import process_document
from ..seed import seed_defaults
from .generate_full_benchmark_plans import LABEL_TEXT, ALT_LABEL_TEXT

PLANS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "testdata" / "titleblocks_full"
FRESH_PLANS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "testdata" / "titleblocks_fresh_acceptance"
TEST_DB_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "test_p28_benchmark.db"
REPORTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "testdata" / "benchmark_reports"

MATCH_THRESHOLD = 90
RUN_SEED = 20261016  # feste Saat, damit auch die 5%-Stichprobe reproduzierbar ist


def _values_match(value: str | None, expected: str | None) -> bool:
    if value is None or expected is None:
        return False
    a = " ".join(value.lower().split())
    b = " ".join(expected.lower().split())
    return fuzz.ratio(a, b) >= MATCH_THRESHOLD


def _fresh_test_session():
    TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    engine = create_engine(f"sqlite:///{TEST_DB_PATH}", connect_args={"check_same_thread": False})
    AppBase.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _empty_bucket():
    return {"hits": 0, "total": 0, "green": 0, "false_green": 0, "no_result": 0}


def _rates(b: dict) -> dict:
    total = b["total"] or 1
    green = b["green"] or 1
    return {
        "hit_rate": round(b["hits"] / total, 4),
        "false_green_rate": round(b["false_green"] / green, 4) if b["green"] else 0.0,
        "no_result_rate": round(b["no_result"] / total, 4),
        "n": b["total"],
        "n_green": b["green"],
    }


EXPECTED_ROTATION_BY_LAYOUT = {
    "rotated90": 270, "rotated180": 180, "rotated270": 90,
}


def _classify_cause(
    field_key, expected, extracted, status, candidates, error_type, document_meta, outcome_kind,
    rotation_mismatch=False, sibling_labels=None, sibling_values=None,
) -> str:
    """Regelbasierte Ursachen-Einordnung fuer den Bericht. Zwei Signale sind
    objektiv messbar und werden deshalb zuerst geprueft: eine falsch
    erkannte Rotation (Vergleich mit der aus dem Layout-Typ bekannten
    Soll-Rotation) und eine Verwechslung mit Beschriftung/Wert eines nahen
    Nachbarfelds (Zeilen-/Zellen-Verschmelzung). Der Rest bleibt eine grobe
    Naeherung."""
    layout = document_meta.get("layout_type")

    if rotation_mismatch:
        return "Rotationserkennung lag falsch - Seite wurde auf dem Kopf/seitlich verarbeitet"

    sibling_labels = sibling_labels or set()
    sibling_values = sibling_values or set()
    if extracted:
        extracted_norm = extracted.strip().lower()
        if any(extracted_norm == lbl.lower() or lbl.lower() in extracted_norm for lbl in sibling_labels):
            return "Nachbarzeile/-zelle verschmolzen - Beschriftung eines anderen Feldes uebernommen"
        if any(extracted_norm == val.lower() for val in sibling_values if val):
            return "Nachbarzeile/-zelle verschmolzen - Wert eines anderen Feldes uebernommen"

    if outcome_kind == "no_result":
        if layout == "no_frame":
            return "Kein Rahmen/Raster - Bereichs-Erkennung findet keinen sicheren Kandidaten"
        if error_type == "missing_date" and field_key == "datum":
            return "Feld tatsaechlich nicht auf dem Blatt vorhanden (korrekt erkannt als fehlend)"
        return "Keine passende Beschriftung oder Formatspur im gewaehlten Bereich gefunden"

    # false_green oder falsch-aber-nicht-gruen
    if error_type == "decoy_text" and extracted and "03.01.2026" in (extracted or ""):
        return "Taeuschend aehnlicher Text ausserhalb des Titelblocks uebernommen"
    if error_type == "handwriting_value":
        return "Handschriftlich wirkende Schrift von Tesseract falsch gelesen"
    if candidates and candidates[0].get("match_type") == "format":
        return "Formatbasierter Kandidat ohne Beschriftungstreffer falsch gewaehlt"
    if candidates and len(candidates) > 1 and candidates[0]["assignment_confidence"] - candidates[1]["assignment_confidence"] < 0.1:
        return "Mehrdeutigkeit zwischen sehr aehnlich bewerteten Kandidaten"
    if error_type in ("degraded_scan",):
        return "Schlechte Scan-Qualitaet (Schiefstand/Unschaerfe) fuehrte zu OCR-Fehllesung"
    if layout == "no_frame":
        return "Kein Rahmen/Raster - Bereich oder Zelle falsch abgegrenzt"
    return "OCR-Lesefehler oder falsch abgegrenzte Zelle (keine eindeutige Ursache automatisch zuordenbar)"


def _dominant_plan_note(cases: list[dict], min_total: int = 3, threshold: float = 0.4) -> str | None:
    """Warnt, wenn ein einzelner Plan einen unverhaeltnismaessig grossen
    Anteil einer Fallliste ausmacht - sonst liest sich z.B. '12 falsch-
    gruene Faelle' nach einem breiten Problem, obwohl es vielleicht nur
    EIN kaputter Plan mit vielen Feldern ist."""
    if len(cases) < min_total:
        return None
    counts = Counter(c["filename"] for c in cases)
    filename, n = counts.most_common(1)[0]
    share = n / len(cases)
    if share >= threshold:
        return f"{filename} macht {n} von {len(cases)} Faellen aus ({share*100:.0f}%) - dominiert diese Liste."
    return None


def run_full_benchmark(plans_dir: Path = PLANS_DIR, run_label: str = "haupt") -> dict:
    solutions_path = plans_dir / "loesungen.json"
    if not solutions_path.exists():
        raise FileNotFoundError(
            f"Keine Loesungsdatei unter {solutions_path} - erst "
            "generate_full_benchmark_plans ausfuehren."
        )
    solutions = json.loads(solutions_path.read_text(encoding="utf-8"))

    random.seed(RUN_SEED)
    db = _fresh_test_session()
    seed_defaults(db)

    object_ids = sorted({meta["object_id"] for meta in solutions.values()})
    customers_by_object = {}
    for oid in object_ids:
        customer = Customer(name=f"Testobjekt {oid}")
        db.add(customer)
        db.commit()
        db.refresh(customer)
        customers_by_object[oid] = customer.id

    buckets = {"dev": _empty_bucket(), "acceptance": _empty_bucket()}
    per_field = {"dev": defaultdict(_empty_bucket), "acceptance": defaultdict(_empty_bucket)}
    per_layout = {"dev": defaultdict(_empty_bucket), "acceptance": defaultdict(_empty_bucket)}

    false_green_cases = []
    other_wrong_cases = []
    no_result_cases = []
    cause_counter = Counter()

    extracted_by_object_field = defaultdict(lambda: defaultdict(list))  # object_id -> field_key -> [(filename, value)]
    processing_errors = []

    for filename in sorted(solutions.keys()):
        meta = solutions[filename]
        split = meta["split"]
        customer_id = customers_by_object[meta["object_id"]]

        document = TitleblockDocument(
            customer_id=customer_id, filename=filename, stored_path=str(plans_dir / filename)
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        try:
            process_document(db, document)
        except Exception as exc:
            processing_errors.append({"filename": filename, "error": str(exc)})
            continue

        results = db.query(DocumentFieldResult).filter_by(document_id=document.id).all()
        results_by_key = {r.field_key: r for r in results}

        chosen_region = db.query(DocumentRegion).filter_by(document_id=document.id, is_chosen=True).first()
        expected_rotation = EXPECTED_ROTATION_BY_LAYOUT.get(meta["layout_type"], 0)
        rotation_mismatch = chosen_region is not None and chosen_region.rotation != expected_rotation

        all_labels = ALT_LABEL_TEXT if meta["error_type"] == "alt_labels_and_font" else LABEL_TEXT
        sibling_values_all = set(meta["fields"].values())

        all_field_keys = set(meta["fields"].keys()) | set(results_by_key.keys())
        for field_key in all_field_keys:
            expected = meta["fields"].get(field_key)
            result = results_by_key.get(field_key)
            status = result.status.value if result else "red"
            candidates = json.loads(result.candidates_json) if result and result.candidates_json else []
            extracted = candidates[0]["value"] if candidates else None

            if expected is None:
                correct = status == "red"
            else:
                correct = status != "red" and _values_match(extracted, expected)

            if field_key == "flurstueck" and expected is not None:
                extracted_by_object_field[meta["object_id"]]["flurstueck"].append((filename, extracted, expected))

            for scope in (buckets[split], per_field[split][field_key], per_layout[split][meta["layout_type"]]):
                scope["total"] += 1
                scope["hits"] += int(correct)
                if status == "green":
                    scope["green"] += 1
                    if not correct:
                        scope["false_green"] += 1
                if status == "red":
                    scope["no_result"] += 1

            if not correct:
                sibling_labels = {v for k, v in all_labels.items() if k != field_key}
                sibling_values = sibling_values_all - {expected} if expected else sibling_values_all
                case = {
                    "filename": filename, "field_key": field_key, "split": split,
                    "layout_type": meta["layout_type"], "error_type": meta["error_type"],
                    "status": status, "expected": expected, "extracted": extracted,
                    "candidates": candidates, "rotation_mismatch": rotation_mismatch,
                }
                classify_args = (field_key, expected, extracted, status, candidates, meta["error_type"], meta)
                classify_kwargs = dict(rotation_mismatch=rotation_mismatch, sibling_labels=sibling_labels, sibling_values=sibling_values)
                if status == "green":
                    cause = _classify_cause(*classify_args, "false_green", **classify_kwargs)
                    case["likely_cause"] = cause
                    cause_counter[cause] += 1
                    false_green_cases.append(case)
                elif status == "red":
                    if expected is not None:  # nur zaehlen, wenn tatsaechlich etwas erwartet war
                        cause = _classify_cause(*classify_args, "no_result", **classify_kwargs)
                        case["likely_cause"] = cause
                        cause_counter[cause] += 1
                        no_result_cases.append(case)
                else:  # gelb, aber falsch
                    cause = _classify_cause(*classify_args, "wrong_not_green", **classify_kwargs)
                    case["likely_cause"] = cause
                    cause_counter[cause] += 1
                    other_wrong_cases.append(case)

    # ---- Stichprobenkontrolle: automatisiert anhand der Loesungsdatei ausgewertet ----
    sample_checks = db.query(GreenSampleCheck).all()
    sample_total = len(sample_checks)
    sample_wrong = 0
    for check in sample_checks:
        doc = db.get(TitleblockDocument, check.document_id)
        meta = solutions.get(doc.filename)
        if meta is None:
            continue
        result = (
            db.query(DocumentFieldResult)
            .filter_by(document_id=check.document_id, field_key=check.field_key)
            .first()
        )
        candidates = json.loads(result.candidates_json) if result and result.candidates_json else []
        extracted = candidates[0]["value"] if candidates else None
        expected = meta["fields"].get(check.field_key)
        ok = _values_match(extracted, expected) if expected is not None else False
        if not ok:
            sample_wrong += 1

    # ---- Kreuz-Konsistenz: gleiches Objekt, abweichendes Flurstueck ----
    consistency_findings = []
    for object_id, field_data in extracted_by_object_field.items():
        entries = field_data.get("flurstueck", [])
        extracted_values = {e[1] for e in entries if e[1]}
        if len(extracted_values) > 1:
            consistency_findings.append({
                "object_id": object_id,
                "field_key": "flurstueck",
                "values_found": [{"filename": fn, "extracted": v, "expected": exp} for fn, v, exp in entries],
            })

    top_causes = cause_counter.most_common(3)

    dominant_plan_notes = {
        "false_green": _dominant_plan_note(false_green_cases),
        "no_result": _dominant_plan_note(no_result_cases),
        "other_wrong": _dominant_plan_note(other_wrong_cases),
    }
    dominant_plan_notes = {k: v for k, v in dominant_plan_notes.items() if v}

    report = {
        "run_label": run_label,
        "run_at": datetime.utcnow().isoformat(),
        "plan_count": len(solutions),
        "dev_count": sum(1 for m in solutions.values() if m["split"] == "dev"),
        "acceptance_count": sum(1 for m in solutions.values() if m["split"] == "acceptance"),
        "error_plan_count": sum(1 for m in solutions.values() if m["error_type"] is not None),
        "processing_errors": processing_errors,
        "overall": {split: _rates(buckets[split]) for split in ("dev", "acceptance")},
        "per_field": {
            split: {k: _rates(v) for k, v in per_field[split].items()} for split in ("dev", "acceptance")
        },
        "per_layout_type": {
            split: {k: _rates(v) for k, v in per_layout[split].items()} for split in ("dev", "acceptance")
        },
        "false_green_cases": false_green_cases,
        "other_wrong_cases": other_wrong_cases,
        "no_result_cases": no_result_cases,
        "sample_check": {
            "total_sampled": sample_total,
            "wrong": sample_wrong,
            "wrong_rate": round(sample_wrong / sample_total, 4) if sample_total else None,
            "note": "Automatisiert anhand der Loesungsdatei ausgewertet (kein Mensch beteiligt) - "
                    "fuer den echten Betrieb entscheidet stattdessen ein Mensch je Stichprobe.",
        },
        "cross_document_consistency": consistency_findings,
        "top_causes": [{"cause": c, "count": n} for c, n in top_causes],
        "dominant_plan_notes": dominant_plan_notes,
    }

    db.close()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()  # keine synthetischen Testdaten dauerhaft liegen lassen

    return report


def _fmt_pct(x) -> str:
    return f"{x*100:.1f}%" if x is not None else "n/v"


def _append_report_markdown(report: dict, lines: list[str]) -> None:
    label = report.get("run_label", "haupt")
    lines.append(f"# P28 Pruefstand-Bericht [{label}] - {report['run_at']}")
    lines.append("")
    lines.append(f"Testplaene gesamt: {report['plan_count']} "
                 f"(dev={report['dev_count']}, acceptance={report['acceptance_count']}, "
                 f"mit Fehlerfall={report['error_plan_count']})")
    if report["processing_errors"]:
        lines.append(f"\n**ACHTUNG:** {len(report['processing_errors'])} Plaene konnten nicht verarbeitet werden:")
        for e in report["processing_errors"]:
            lines.append(f"- {e['filename']}: {e['error']}")
    lines.append("")

    for split in ("dev", "acceptance"):
        o = report["overall"][split]
        if o["n"] == 0:
            continue
        lines.append(f"## Gruppe: {split} (n={o['n']} Felder)")
        lines.append(f"- Trefferquote gesamt: **{_fmt_pct(o['hit_rate'])}** (n={o['n']})")
        lines.append(f"- Falsch-gruen-Quote: **{_fmt_pct(o['false_green_rate'])}** (Ziel: nahe 0; n_gruen={o['n_green']})")
        lines.append(f"- Anteil ohne Ergebnis (rot): {_fmt_pct(o['no_result_rate'])} (n={o['n']})")
        lines.append("")
        lines.append("Je Feld:")
        for k, r in sorted(report["per_field"][split].items()):
            lines.append(f"  - {k}: Treffer {_fmt_pct(r['hit_rate'])} (n={r['n']}), falsch-gruen {_fmt_pct(r['false_green_rate'])} (n_gruen={r['n_green']})")
        lines.append("")
        lines.append("Je Layout-Typ:")
        for k, r in sorted(report["per_layout_type"][split].items()):
            lines.append(f"  - {k}: Treffer {_fmt_pct(r['hit_rate'])} (n={r['n']}), falsch-gruen {_fmt_pct(r['false_green_rate'])} (n_gruen={r['n_green']})")
        lines.append("")

    lines.append(f"## Falsch-gruene Faelle (n={len(report['false_green_cases'])})")
    if not report["false_green_cases"]:
        lines.append("Keine.")
    else:
        if "false_green" in report["dominant_plan_notes"]:
            lines.append(f"**Hinweis:** {report['dominant_plan_notes']['false_green']}")
        for c in report["false_green_cases"]:
            lines.append(
                f"- [{c['split']}] {c['filename']} / Feld '{c['field_key']}': "
                f"erkannt='{c['extracted']}' erwartet='{c['expected']}' - Ursache: {c['likely_cause']}"
            )
    lines.append("")

    lines.append(f"## Stichprobenkontrolle (automatisiert anhand der Loesungsdatei, n={report['sample_check']['total_sampled']})")
    sc = report["sample_check"]
    lines.append(f"- Vorgelegte gruene Zellen: {sc['total_sampled']}")
    lines.append(f"- davon falsch: {sc['wrong']} von {sc['total_sampled']} ({_fmt_pct(sc['wrong_rate'])})")
    lines.append(f"- {sc['note']}")
    lines.append("")

    lines.append("## Kreuz-Konsistenz (gleiches Objekt, abweichendes Flurstueck)")
    if not report["cross_document_consistency"]:
        lines.append("Keine Abweichung erkannt.")
    else:
        for f in report["cross_document_consistency"]:
            lines.append(f"- Objekt {f['object_id']}: {f['values_found']}")
    lines.append("")

    lines.append(f"## Drei haeufigste Fehlerursachen (Basis: {sum(i['count'] for i in report['top_causes'])} von allen Fehlfaellen)")
    for item in report["top_causes"]:
        lines.append(f"- {item['cause']} ({item['count']}x)")
    for key, note in report["dominant_plan_notes"].items():
        if key != "false_green":
            lines.append(f"\n**Hinweis ({key}):** {note}")
    lines.append("")


def _write_markdown(report: dict, path: Path, extra_report: dict | None = None) -> None:
    lines: list[str] = []
    _append_report_markdown(report, lines)
    if extra_report is not None:
        lines.append("---")
        lines.append("")
        _append_report_markdown(extra_report, lines)
    path.write_text("\n".join(lines), encoding="utf-8")


def store_run(report: dict, json_path: Path, md_path: Path) -> None:
    from ...database import SessionLocal as AppSessionLocal
    from ...database import engine as app_engine
    from ..models import FullBenchmarkRun

    AppBase.metadata.create_all(bind=app_engine)
    db = AppSessionLocal()
    try:
        summary_without_cases = {k: v for k, v in report.items() if k not in ("false_green_cases", "other_wrong_cases", "no_result_cases")}
        db.add(
            FullBenchmarkRun(
                plan_count=report["plan_count"],
                dev_count=report["dev_count"],
                acceptance_count=report["acceptance_count"],
                dev_hit_rate=report["overall"]["dev"]["hit_rate"],
                dev_false_green_rate=report["overall"]["dev"]["false_green_rate"],
                dev_no_result_rate=report["overall"]["dev"]["no_result_rate"],
                acceptance_hit_rate=report["overall"]["acceptance"]["hit_rate"],
                acceptance_false_green_rate=report["overall"]["acceptance"]["false_green_rate"],
                acceptance_no_result_rate=report["overall"]["acceptance"]["no_result_rate"],
                report_json_path=str(json_path),
                report_markdown_path=str(md_path),
                summary_json=json.dumps(summary_without_cases, ensure_ascii=False),
            )
        )
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    report = run_full_benchmark(PLANS_DIR, run_label="haupt (31+ Plaene, dev/acceptance)")

    fresh_report = None
    if (FRESH_PLANS_DIR / "loesungen.json").exists():
        fresh_report = run_full_benchmark(FRESH_PLANS_DIR, run_label="frische Abnahmegruppe (neuer Zufallswert, nie zum Nachbessern verwendet)")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    json_path = REPORTS_DIR / f"p28_report_{stamp}.json"
    md_path = REPORTS_DIR / f"p28_report_{stamp}.md"

    combined = {"main": report, "fresh_acceptance": fresh_report}
    json_path.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(report, md_path, fresh_report)
    store_run(report, json_path, md_path)

    print(f"Bericht gespeichert: {md_path}")
    print(f"Rohdaten: {json_path}")
    print()
    for split in ("dev", "acceptance"):
        o = report["overall"][split]
        print(f"[Haupt/{split}] Trefferquote={_fmt_pct(o['hit_rate'])}  Falsch-gruen={_fmt_pct(o['false_green_rate'])}  Ohne Ergebnis={_fmt_pct(o['no_result_rate'])}")
    if fresh_report is not None:
        o = fresh_report["overall"]["acceptance"]
        print(f"[Frische Abnahmegruppe] Trefferquote={_fmt_pct(o['hit_rate'])}  Falsch-gruen={_fmt_pct(o['false_green_rate'])}  Ohne Ergebnis={_fmt_pct(o['no_result_rate'])}")
