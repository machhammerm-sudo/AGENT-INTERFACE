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
GREEN_MIN_WORD_OCR = 55.0  # UND das schwaechste Wort im Wert darf nicht zu unsicher gelesen sein
GREEN_MAX_CHARS = 50  # auffaellig lange Werte (oft verschmolzene Nachbarzellen) nie gruen
GREEN_MAX_WORDS = 6

# Format-Muster, die distinktiv genug sind, um als "fremdes Formatmuster"
# in einem ANDEREN Feld zu gelten (Plannummer/Index/Flurstueck sind zu
# generisch - fast jede Zahl wuerde faelschlich als Kontamination gelten).
DISTINCTIVE_FORMAT_FIELDS = {"datum", "massstab", "flaeche"}


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

    @property
    def min_conf(self) -> float:
        confs = [w.conf for w in self.words if w.conf >= 0]
        return min(confs) if confs else 0.0


@dataclass
class FieldCandidate:
    value: str
    assignment_confidence: float
    ocr_confidence: float
    match_type: str  # "same_line" | "below" | "right_of_label_row" | "format"
    label_score: float
    rel_bbox: tuple[float, float, float, float]
    min_word_confidence: float = 0.0


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


ROW_TOLERANCE_FACTOR = 0.4  # Anteil der (globalen) Text-Mittelhoehe, der eine Zeile definiert


def _group_lines(words: list[Word]) -> list[Line]:
    """Gruppiert Woerter geometrisch zu Zeilen UND Zellen (nicht ueber
    Tesseracts eigene block/par/line-Kennung, die bei engen Rastern Spalten
    gerne zu einer einzigen 'Zeile' zusammenwirft). Erst nach Zeilenhoehe
    clustern, dann innerhalb der Zeile an groesseren Luecken in Zellen
    auftrennen - genau diese Luecken trennen i.d.R. Beschriftungs- von
    Wertspalte in einem Titelblock-Raster.

    Die Zeilen-Zuordnung arbeitet ueber den vertikalen MITTELPUNKT jedes
    Wortes gegen den LAUFENDEN MITTELWERT der Zeile (statt wachsender
    Min/Max-Grenzen, die bei eng stehenden Zeilen schnell ineinanderlaufen
    koennen) und nutzt eine feste, aus der globalen Median-Texthoehe
    abgeleitete Toleranz - das bleibt robust, auch wenn ein einzelnes Wort
    zufaellig hoeher oder tiefer sitzt."""
    if not words:
        return []

    heights = sorted(w.height for w in words)
    median_height = heights[len(heights) // 2]
    tolerance = max(median_height * ROW_TOLERANCE_FACTOR, 4)

    ordered = sorted(words, key=lambda w: (w.top + w.bottom) / 2)
    rows: list[list[Word]] = []
    for w in ordered:
        w_center = (w.top + w.bottom) / 2
        placed = False
        for row in rows:
            row_center = sum((r.top + r.bottom) / 2 for r in row) / len(row)
            if abs(w_center - row_center) <= tolerance:
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
                    min_word_confidence=line.min_conf,
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


def _contains_foreign_signal(value: str, own_field_key: str, all_specs: list["FieldSpec"]) -> bool:
    """True, wenn der Wert eine Beschriftung oder ein distinktives
    Formatmuster eines ANDEREN Feldes enthaelt - ein starkes Indiz fuer
    eine verschmolzene Nachbarzeile/-zelle, die nie gruen werden soll."""
    value_norm = value.strip()
    if not value_norm:
        return False

    for spec in all_specs:
        if spec.field_key == own_field_key:
            continue
        for syn in spec.synonyms:
            if len(syn) < 4:
                continue
            if re.search(r"\b" + re.escape(syn) + r"\b", value_norm, re.IGNORECASE):
                return True
        if spec.field_key in DISTINCTIVE_FORMAT_FIELDS and spec.format_regex:
            try:
                if re.search(spec.format_regex, value_norm, re.IGNORECASE):
                    return True
            except re.error:
                pass
    return False


def _looks_too_long(value: str) -> bool:
    return len(value) > GREEN_MAX_CHARS or len(value.split()) > GREEN_MAX_WORDS


EDGE_TRUNCATION_MARGIN = 0.02  # Kandidat, dessen Box bis auf 2% an den Ausschnittsrand reicht, gilt als moeglich abgeschnitten


def _touches_crop_edge(rel_bbox: tuple[float, float, float, float], margin: float = EDGE_TRUNCATION_MARGIN) -> bool:
    """True, wenn die Kandidaten-Box bis an den Rand des Titelblock-
    Ausschnitts reicht - ein starkes, geometrisches Indiz dafuer, dass der
    Wert dort abgeschnitten wurde (der Text haette eigentlich weitergehen
    koennen). OCR kann so einen abgeschnittenen Rest trotzdem mit hoher
    Sicherheit (falsch) lesen, deshalb reicht die OCR-Sicherheit allein
    nicht als Schutz."""
    x, y, w, h = rel_bbox
    return x <= margin or y <= margin or (x + w) >= 1 - margin or (y + h) >= 1 - margin


def status_from_candidates(
    candidates: list[FieldCandidate],
    has_frame: bool = True,
    own_field_key: str | None = None,
    all_specs: list["FieldSpec"] | None = None,
) -> str:
    if not candidates:
        return "red"
    top = candidates[0]

    # Ohne Rahmen/Raster ist die Bereichs- und Zellenabgrenzung grundsaetzlich
    # unsicherer (siehe Pruefstand P28) - ein solches Feld wird nie gruen,
    # auch nicht bei hoher Zuordnungssicherheit.
    if not has_frame:
        return "yellow"

    # Gruen braucht: eindeutige Zuordnung, sichere OCR-Lesung IM MITTEL,
    # sicheres schwaechstes Wort, ein plausibel kurzer Wert, und keine
    # erkennbare Verunreinigung durch ein fremdes Feld.
    if (
        top.assignment_confidence >= GREEN_THRESHOLD
        and top.ocr_confidence >= GREEN_OCR_MIN
        and top.min_word_confidence >= GREEN_MIN_WORD_OCR
        and not _looks_too_long(top.value)
        and not _touches_crop_edge(top.rel_bbox)
        and (all_specs is None or own_field_key is None or not _contains_foreign_signal(top.value, own_field_key, all_specs))
    ):
        if len(candidates) == 1 or candidates[1].assignment_confidence < top.assignment_confidence * GREEN_MARGIN:
            return "green"
    return "yellow"


def _looks_like_a_label(text: str, all_synonyms: list[str]) -> bool:
    """True, wenn der Zellentext selbst eher nach einer Beschriftung als
    nach einem Wert aussieht - verhindert, dass die Beschriftungszelle der
    naechsten Zeile/Spalte faelschlich als Wertkandidat uebernommen wird."""
    return any(fuzz.ratio(text.lower().rstrip(":."), syn.lower()) >= LABEL_MATCH_THRESHOLD for syn in all_synonyms)


def extract_fields(
    region_image: Image.Image, fields: list[FieldSpec], has_frame: bool = True
) -> list[FieldExtractionResult]:
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
                remainder_confs = [w.conf for w in remainder_words if w.conf >= 0]
                conf = sum(remainder_confs) / len(remainder_confs) if remainder_confs else 0.0
                min_conf = min(remainder_confs) if remainder_confs else 0.0
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
                        min_word_confidence=min_conf,
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
                            min_word_confidence=other.min_conf,
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
                        min_word_confidence=below.min_conf,
                    )
                )

        if spec.format_regex:
            candidates.extend(_format_candidates(lines, spec.format_regex, image_size))

        deduped = _dedupe_keep_best(candidates)[:3]
        status = status_from_candidates(deduped, has_frame, spec.field_key, fields)
        results.append(FieldExtractionResult(field_key=spec.field_key, status=status, candidates=deduped))

    return results
