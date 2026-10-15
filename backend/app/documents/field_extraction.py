"""Stufe B: Felder zuordnen - nicht positionsgebunden, rein lokal.

Fuer jedes Feld wird die Beschriftung per unscharfem Vergleich im Titelblock-
Bereich gesucht. Wertkandidaten entstehen aus der Umgebung (gleiche Zeile,
rechts, darunter) sowie zusaetzlich formatbasiert (Datum, Massstab, ...),
auch ganz ohne Beschriftungstreffer. Jeder Kandidat traegt eine
ZUORDNUNGS-SICHERHEIT, getrennt von der OCR-Lesesicherheit.
"""

import re
from dataclasses import dataclass, field

import pytesseract
from PIL import Image
from rapidfuzz import fuzz

LABEL_MATCH_THRESHOLD = 72
MAX_LABEL_WINDOW_WORDS = 4
ROW_OVERLAP_MIN = 0.4  # Anteil ueberlappender Hoehe, um "gleiche Zeile" ueber Spalten hinweg zu gelten

GREEN_THRESHOLD = 0.72
GREEN_MARGIN = 0.78  # zweiter Kandidat muss unter top*margin bleiben, sonst nur gelb
GREEN_OCR_MIN = 70.0  # auch eine eindeutige Zuordnung bleibt gelb, wenn das OCR-Lesen selbst unsicher war


@dataclass
class FieldSpec:
    field_key: str
    label: str
    synonyms: list[str]
    format_regex: str | None


@dataclass
class Word:
    text: str
    left: int
    top: int
    width: int
    height: int
    conf: float
    block: int
    par: int
    line: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height


@dataclass
class Line:
    words: list[Word]

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def left(self) -> int:
        return min(w.left for w in self.words)

    @property
    def right(self) -> int:
        return max(w.right for w in self.words)

    @property
    def top(self) -> int:
        return min(w.top for w in self.words)

    @property
    def bottom(self) -> int:
        return max(w.bottom for w in self.words)

    @property
    def mean_conf(self) -> float:
        confs = [w.conf for w in self.words if w.conf >= 0]
        return sum(confs) / len(confs) if confs else 0.0


@dataclass
class FieldCandidate:
    value: str
    assignment_confidence: float
    ocr_confidence: float
    match_type: str  # "same_line" | "below" | "right_of_label_row" | "format"
    label_score: float
    rel_bbox: tuple[float, float, float, float]


@dataclass
class FieldExtractionResult:
    field_key: str
    status: str  # "green" | "yellow" | "red"
    candidates: list[FieldCandidate] = field(default_factory=list)


def _extract_words(image: Image.Image) -> list[Word]:
    data = pytesseract.image_to_data(
        image, lang="deu+eng", output_type=pytesseract.Output.DICT
    )
    words = []
    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        if not text:
            continue
        words.append(
            Word(
                text=text,
                left=data["left"][i],
                top=data["top"][i],
                width=data["width"][i],
                height=data["height"][i],
                conf=float(data["conf"][i]),
                block=data["block_num"][i],
                par=data["par_num"][i],
                line=data["line_num"][i],
            )
        )
    return words


def _group_lines(words: list[Word]) -> list[Line]:
    """Gruppiert Woerter geometrisch zu Zeilen UND Zellen (nicht ueber
    Tesseracts eigene block/par/line-Kennung, die bei engen Rastern Spalten
    gerne zu einer einzigen 'Zeile' zusammenwirft). Erst nach Zeilenhoehe
    clustern, dann innerhalb der Zeile an groesseren Luecken in Zellen
    auftrennen - genau diese Luecken trennen i.d.R. Beschriftungs- von
    Wertspalte in einem Titelblock-Raster."""
    if not words:
        return []

    ordered = sorted(words, key=lambda w: w.top)
    rows: list[list[Word]] = []
    for w in ordered:
        placed = False
        for row in rows:
            row_top = min(r.top for r in row)
            row_bottom = max(r.bottom for r in row)
            tolerance = max(r.height for r in row) * 0.5
            if w.top < row_bottom + tolerance and w.bottom > row_top - tolerance:
                row.append(w)
                placed = True
                break
        if not placed:
            rows.append([w])

    cells: list[Line] = []
    for row in rows:
        row.sort(key=lambda w: w.left)
        row_height = max(w.height for w in row)
        # Ein Spaltenwechsel in einer Tabellenzeile zeigt sich als Luecke,
        # die deutlich groesser ist als ein normaler Wortabstand - laesst
        # sich an der Zeilenhoehe festmachen (robuster als ein Median ueber
        # evtl. nur 1-2 Luecken pro Zeile).
        gap_threshold = max(row_height * 1.0, 15)

        current_cell = [row[0]]
        for prev, cur in zip(row, row[1:]):
            if cur.left - prev.right > gap_threshold:
                cells.append(Line(words=current_cell))
                current_cell = [cur]
            else:
                current_cell.append(cur)
        cells.append(Line(words=current_cell))

    cells.sort(key=lambda l: (l.top, l.left))
    return cells


def _best_label_window(line: Line, synonyms: list[str]) -> tuple[float, int]:
    """Prueft, ob die ersten 1..MAX_LABEL_WINDOW_WORDS Woerter der Zeile zu
    einem Synonym passen. Gibt (bester_score, anzahl_woerter_im_fenster) zurueck."""
    best_score, best_count = 0.0, 0
    max_window = min(MAX_LABEL_WINDOW_WORDS, len(line.words))
    for count in range(1, max_window + 1):
        window_text = " ".join(w.text for w in line.words[:count])
        for syn in synonyms:
            score = fuzz.ratio(window_text.lower().rstrip(":."), syn.lower())
            if score > best_score:
                best_score, best_count = score, count
    return best_score, best_count


def _row_overlap(a: Line, b: Line) -> float:
    top = max(a.top, b.top)
    bottom = min(a.bottom, b.bottom)
    if bottom <= top:
        return 0.0
    overlap = bottom - top
    return overlap / min(a.bottom - a.top, b.bottom - b.top)


def _rel_bbox(obj, image_size: tuple[int, int]) -> tuple[float, float, float, float]:
    w, h = image_size
    return (obj.left / w, obj.top / h, (obj.right - obj.left) / w, (obj.bottom - obj.top) / h)


def _format_candidates(
    lines: list[Line], pattern: str, image_size: tuple[int, int]
) -> list[FieldCandidate]:
    regex = re.compile(pattern, re.IGNORECASE)
    candidates = []
    for line in lines:
        match = regex.search(line.text)
        if match:
            candidates.append(
                FieldCandidate(
                    value=match.group(0),
                    assignment_confidence=0.55,  # Format allein, ohne Beschriftung -> moderat
                    ocr_confidence=line.mean_conf,
                    match_type="format",
                    label_score=0.0,
                    rel_bbox=_rel_bbox(line, image_size),
                )
            )
    return candidates


def _dedupe_keep_best(candidates: list[FieldCandidate]) -> list[FieldCandidate]:
    best_by_value: dict[str, FieldCandidate] = {}
    for c in candidates:
        key = c.value.strip().lower()
        if not key:
            continue
        existing = best_by_value.get(key)
        if existing is None or c.assignment_confidence > existing.assignment_confidence:
            best_by_value[key] = c
    return sorted(best_by_value.values(), key=lambda c: c.assignment_confidence, reverse=True)


def status_from_candidates(candidates: list[FieldCandidate]) -> str:
    if not candidates:
        return "red"
    top = candidates[0]
    # Gruen braucht BEIDES: eine eindeutige Zuordnung UND eine sichere
    # OCR-Lesung - eine klare Zuordnung rettet nichts, wenn Tesseract sich
    # beim eigentlichen Zeichen-Lesen selbst schon unsicher war.
    if top.assignment_confidence >= GREEN_THRESHOLD and top.ocr_confidence >= GREEN_OCR_MIN:
        if len(candidates) == 1 or candidates[1].assignment_confidence < top.assignment_confidence * GREEN_MARGIN:
            return "green"
    return "yellow"


def _looks_like_a_label(text: str, all_synonyms: list[str]) -> bool:
    """True, wenn der Zellentext selbst eher nach einer Beschriftung als
    nach einem Wert aussieht - verhindert, dass die Beschriftungszelle der
    naechsten Zeile/Spalte faelschlich als Wertkandidat uebernommen wird."""
    return any(fuzz.ratio(text.lower().rstrip(":."), syn.lower()) >= LABEL_MATCH_THRESHOLD for syn in all_synonyms)


def extract_fields(region_image: Image.Image, fields: list[FieldSpec]) -> list[FieldExtractionResult]:
    words = _extract_words(region_image)
    lines = _group_lines(words)
    image_size = region_image.size
    all_synonyms = [syn for spec in fields for syn in spec.synonyms]

    results = []
    for spec in fields:
        candidates: list[FieldCandidate] = []

        for i, line in enumerate(lines):
            label_score, window_count = _best_label_window(line, spec.synonyms)
            if label_score < LABEL_MATCH_THRESHOLD:
                continue

            remainder_words = line.words[window_count:]
            if remainder_words:
                value = " ".join(w.text for w in remainder_words)
                conf = sum(w.conf for w in remainder_words if w.conf >= 0) / max(
                    1, len([w for w in remainder_words if w.conf >= 0])
                )
                candidates.append(
                    FieldCandidate(
                        value=value,
                        assignment_confidence=min(1.0, 0.5 + label_score / 200 + 0.2),
                        ocr_confidence=conf,
                        match_type="same_line",
                        label_score=label_score,
                        rel_bbox=_rel_bbox(
                            type("B", (), {
                                "left": remainder_words[0].left, "top": line.top,
                                "right": remainder_words[-1].right, "bottom": line.bottom,
                            })(),
                            image_size,
                        ),
                    )
                )

            # Beschriftung steht evtl. komplett allein in der Zeile - Wert
            # koennte rechts (andere Spalte, gleiche Zeilenhoehe) oder
            # darunter stehen.
            for other in lines:
                if other is line or _looks_like_a_label(other.text, all_synonyms):
                    continue
                if _row_overlap(line, other) >= ROW_OVERLAP_MIN and other.left > line.right:
                    candidates.append(
                        FieldCandidate(
                            value=other.text,
                            assignment_confidence=min(1.0, 0.45 + label_score / 200 + 0.15),
                            ocr_confidence=other.mean_conf,
                            match_type="right_of_label_row",
                            label_score=label_score,
                            rel_bbox=_rel_bbox(other, image_size),
                        )
                    )

            # Naechste Zelle UNTERHALB in etwa gleicher Spalte (kein Sprung
            # in eine andere Zelle) - per Geometrie gesucht, nicht ueber den
            # Listenindex, da eine Zeile mehrere Zellen enthalten kann.
            below_candidates = [
                other for other in lines
                if other is not line
                and other.top > line.bottom
                and abs(other.left - line.left) < region_image.width * 0.08
                and not _looks_like_a_label(other.text, all_synonyms)
            ]
            if below_candidates:
                below = min(below_candidates, key=lambda o: o.top)
                candidates.append(
                    FieldCandidate(
                        value=below.text,
                        assignment_confidence=min(1.0, 0.4 + label_score / 200 + 0.1),
                        ocr_confidence=below.mean_conf,
                        match_type="below",
                        label_score=label_score,
                        rel_bbox=_rel_bbox(below, image_size),
                    )
                )

        if spec.format_regex:
            candidates.extend(_format_candidates(lines, spec.format_regex, image_size))

        deduped = _dedupe_keep_best(candidates)[:3]
        status = status_from_candidates(deduped)
        results.append(FieldExtractionResult(field_key=spec.field_key, status=status, candidates=deduped))

    return results
