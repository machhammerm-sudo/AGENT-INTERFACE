"""Stufe A: Titelblock-Bereich finden - layoutunabhaengig, rein lokal.

Der Bereich ist NICHT an eine feste Ecke gebunden. Eckennaehe fliesst nur als
schwacher Bonus ein. Grundlage sind zwei Hinweise, die kombiniert werden:
  1. Rahmen-/Linienraster-Dichte (klassische Bildverarbeitung mit OpenCV)
  2. Dichte bekannter Feld-Beschriftungen (grobe OCR-Lesung + unscharfer
     Abgleich gegen die Synonym-Listen)
Fehlt jeder erkennbare Rahmen und jede erkennbare Beschriftung, gilt die
ganze Seite als Bereich, mit niedriger Sicherheit markiert.
"""

from dataclasses import dataclass, field

import cv2
import numpy as np
import pytesseract
from PIL import Image
from rapidfuzz import fuzz

ROTATIONS = (0, 90, 180, 270)
GRID_CELLS = 24  # Seite wird in ein 24x24-Raster fuer die Dichte-Analyse geteilt
CORNER_BONUS_WEIGHT = 0.08  # bewusst klein - nur ein schwacher Bonus, keine Bedingung
MERGE_IOU_THRESHOLD = 0.35


@dataclass
class RegionCandidate:
    rel_x: float
    rel_y: float
    rel_w: float
    rel_h: float
    score: float
    method: str  # "grid" | "label_density" | "fallback_full_page"
    details: dict = field(default_factory=dict)


def detect_rotation(image: Image.Image) -> int:
    """Gibt 0/90/180/270 zurueck. Versucht zuerst Tesseracts
    Orientierungserkennung (OSD); schlaegt das fehl (z.B. zu wenig Text auf
    der Seite), wird ersatzweise bei jeder der vier Drehungen grob OCR
    gelesen und die mit der hoechsten Text-Erkennungsguete gewaehlt."""
    try:
        osd = pytesseract.image_to_osd(image, config="--psm 0")
        for line in osd.splitlines():
            if line.lower().startswith("rotate:"):
                angle = int(line.split(":")[1].strip())
                # Tesseract gibt den Winkel an, um den im Uhrzeigersinn
                # gedreht werden muesste, um die Seite aufzurichten.
                return angle % 360
    except pytesseract.TesseractError:
        pass

    return _detect_rotation_by_text_density(image)


def _detect_rotation_by_text_density(image: Image.Image) -> int:
    # kleine Vorschau genuegt und haelt diesen Fallback schnell
    preview = image.copy()
    preview.thumbnail((1000, 1000))

    best_rotation, best_score = 0, -1.0
    for rotation in ROTATIONS:
        candidate = _rotate(preview, rotation)
        try:
            data = pytesseract.image_to_data(
                candidate, lang="deu+eng", config="--psm 11",
                output_type=pytesseract.Output.DICT,
            )
        except pytesseract.TesseractError:
            continue
        score = 0.0
        for text, conf in zip(data["text"], data["conf"]):
            conf = float(conf)
            if len(text.strip()) >= 3 and conf > 0:
                score += conf
        if score > best_score:
            best_score, best_rotation = score, rotation
    return best_rotation


def _rotate(image: Image.Image, rotation: int) -> Image.Image:
    if rotation == 0:
        return image
    # PIL rotiert gegen den Uhrzeigersinn; wir drehen daher mit negativem Winkel.
    return image.rotate(-rotation, expand=True)


def _line_density_grid(gray: np.ndarray) -> np.ndarray:
    """Liefert ein GRID_CELLS x GRID_CELLS Array mit der Liniendichte pro Zelle."""
    h, w = gray.shape
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=60, minLineLength=min(w, h) // 25, maxLineGap=8
    )

    density = np.zeros((GRID_CELLS, GRID_CELLS), dtype=np.float64)
    if lines is None:
        return density

    cell_w, cell_h = w / GRID_CELLS, h / GRID_CELLS
    for line in lines[:, 0]:
        x1, y1, x2, y2 = line
        angle = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
        is_horizontal = angle < 10 or angle > 170
        is_vertical = 80 < angle < 100
        if not (is_horizontal or is_vertical):
            continue  # nur achsparallele Linien zaehlen als Rasterhinweis

        length = np.hypot(x2 - x1, y2 - y1)
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        gx = min(int(cx / cell_w), GRID_CELLS - 1)
        gy = min(int(cy / cell_h), GRID_CELLS - 1)
        density[gy, gx] += length

    return density


def _find_dense_clusters(density: np.ndarray, min_score: float) -> list[tuple[int, int, int, int, float]]:
    """Einfaches Connected-Components auf einer binarisierten Dichte-Maske,
    liefert (gx0, gy0, gx1, gy1, summierter_score) je Cluster."""
    mask = (density > min_score).astype(np.uint8)
    if mask.sum() == 0:
        return []

    num_labels, labels = cv2.connectedComponents(mask, connectivity=8)
    clusters = []
    for label_id in range(1, num_labels):
        ys, xs = np.where(labels == label_id)
        if len(xs) == 0:
            continue
        gx0, gx1 = int(xs.min()), int(xs.max())
        gy0, gy1 = int(ys.min()), int(ys.max())
        score = float(density[labels == label_id].sum())
        clusters.append((gx0, gy0, gx1, gy1, score))
    return clusters


def _grid_candidates(gray: np.ndarray) -> list[RegionCandidate]:
    h, w = gray.shape
    density = _line_density_grid(gray)
    if density.max() == 0:
        return []

    threshold = max(density.mean() * 2.0, density.max() * 0.15)
    clusters = _find_dense_clusters(density, threshold)

    candidates = []
    max_score = max((c[4] for c in clusters), default=1.0)
    for gx0, gy0, gx1, gy1, score in clusters:
        rel_x = gx0 / GRID_CELLS
        rel_y = gy0 / GRID_CELLS
        rel_w = (gx1 - gx0 + 1) / GRID_CELLS
        rel_h = (gy1 - gy0 + 1) / GRID_CELLS

        # zu grosse Flaechen (> 70% der Seite) sind kein Titelblock, sondern
        # z.B. die ganze Zeichnung mit vielen Linien - ausschliessen
        if rel_w * rel_h > 0.7:
            continue

        corner_bonus = _corner_proximity_bonus(rel_x, rel_y, rel_w, rel_h)
        normalized = score / max_score
        candidates.append(
            RegionCandidate(
                rel_x=rel_x,
                rel_y=rel_y,
                rel_w=rel_w,
                rel_h=rel_h,
                score=normalized * (1 - CORNER_BONUS_WEIGHT) + corner_bonus * CORNER_BONUS_WEIGHT,
                method="grid",
                details={"raw_line_score": score},
            )
        )
    return candidates


def _corner_proximity_bonus(rel_x: float, rel_y: float, rel_w: float, rel_h: float) -> float:
    """Schwacher Bonus, wenn der Bereich nahe einer Ecke oder einem Rand
    liegt - NIE eine Bedingung, nur ein Tiebreaker."""
    cx, cy = rel_x + rel_w / 2, rel_y + rel_h / 2
    corners = [(0, 0), (1, 0), (0, 1), (1, 1)]
    min_corner_dist = min(np.hypot(cx - c[0], cy - c[1]) for c in corners)
    edge_dist = min(rel_x, 1 - (rel_x + rel_w), rel_y, 1 - (rel_y + rel_h))
    corner_score = max(0.0, 1 - min_corner_dist)
    edge_score = max(0.0, 1 - edge_dist * 4)
    return max(corner_score, edge_score)


def _label_density_candidates(
    image: Image.Image, label_synonyms: list[str], fuzzy_threshold: int = 80
) -> list[RegionCandidate]:
    if not label_synonyms:
        return []

    data = pytesseract.image_to_data(
        image, lang="deu+eng", output_type=pytesseract.Output.DICT
    )
    w, h = image.size

    hits = []
    n = len(data["text"])
    for i in range(n):
        text = data["text"][i].strip()
        if len(text) < 3:
            continue
        best = max((fuzz.partial_ratio(text.lower(), s.lower()) for s in label_synonyms), default=0)
        if best >= fuzzy_threshold:
            hits.append(
                (data["left"][i], data["top"][i], data["width"][i], data["height"][i], best)
            )

    if not hits:
        return []

    # Hits zu Clustern zusammenfassen (einfaches Grid-Binning wie bei den Linien)
    cell_w, cell_h = w / GRID_CELLS, h / GRID_CELLS
    density = np.zeros((GRID_CELLS, GRID_CELLS), dtype=np.float64)
    for x, y, bw, bh, score in hits:
        cx, cy = x + bw / 2, y + bh / 2
        gx = min(int(cx / cell_w), GRID_CELLS - 1)
        gy = min(int(cy / cell_h), GRID_CELLS - 1)
        density[gy, gx] += score / 100.0

    # Dichte etwas ausweiten (Dilation), damit nahe beieinanderliegende
    # Beschriftungen zu einem gemeinsamen Bereich verschmelzen.
    density = cv2.dilate(density.astype(np.float32), np.ones((3, 3), np.uint8)).astype(np.float64)

    clusters = _find_dense_clusters(density, min_score=density.max() * 0.2 if density.max() > 0 else 0)
    max_score = max((c[4] for c in clusters), default=1.0)

    candidates = []
    for gx0, gy0, gx1, gy1, score in clusters:
        # etwas Rand dazugeben, damit Werte rechts/unterhalb der Beschriftung mit reinpassen
        pad = 2
        rel_x = max(0, gx0 - pad) / GRID_CELLS
        rel_y = max(0, gy0 - pad) / GRID_CELLS
        rel_w = (min(GRID_CELLS, gx1 + pad) - max(0, gx0 - pad) + 1) / GRID_CELLS
        rel_h = (min(GRID_CELLS, gy1 + pad) - max(0, gy0 - pad) + 1) / GRID_CELLS

        corner_bonus = _corner_proximity_bonus(rel_x, rel_y, rel_w, rel_h)
        normalized = score / max_score
        candidates.append(
            RegionCandidate(
                rel_x=rel_x,
                rel_y=rel_y,
                rel_w=min(rel_w, 1 - rel_x),
                rel_h=min(rel_h, 1 - rel_y),
                score=normalized * (1 - CORNER_BONUS_WEIGHT) + corner_bonus * CORNER_BONUS_WEIGHT,
                method="label_density",
                details={"raw_label_score": score},
            )
        )
    return candidates


def _overlap_metrics(a: RegionCandidate, b: RegionCandidate) -> tuple[float, float]:
    """Gibt (IoU, Containment) zurueck. Containment ist der Anteil des
    KLEINEREN Bereichs, der im groesseren steckt - IoU allein uebersieht,
    dass ein kleiner Bereich fast vollstaendig in einem grossen liegen kann
    (z.B. nur die Rasterlinien eines Teilbereichs), ohne dass das
    Flaechenverhaeltnis einen hohen IoU-Wert ergibt."""
    ax0, ay0, ax1, ay1 = a.rel_x, a.rel_y, a.rel_x + a.rel_w, a.rel_y + a.rel_h
    bx0, by0, bx1, by1 = b.rel_x, b.rel_y, b.rel_x + b.rel_w, b.rel_y + b.rel_h
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0, 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    area_a, area_b = a.rel_w * a.rel_h, b.rel_w * b.rel_h
    union = area_a + area_b - inter
    iou = inter / union if union > 0 else 0.0
    containment = inter / min(area_a, area_b) if min(area_a, area_b) > 0 else 0.0
    return iou, containment


CONTAINMENT_THRESHOLD = 0.8


def _merge_overlapping(candidates: list[RegionCandidate]) -> list[RegionCandidate]:
    candidates = sorted(candidates, key=lambda c: c.rel_w * c.rel_h, reverse=True)
    merged: list[RegionCandidate] = []
    for cand in candidates:
        overlap = next(
            (
                m for m in merged
                if (lambda iou, containment: iou > MERGE_IOU_THRESHOLD or containment > CONTAINMENT_THRESHOLD)
                (*_overlap_metrics(cand, m))
            ),
            None,
        )
        if overlap is None:
            merged.append(cand)
        else:
            # Bereich der beiden kombinieren (Bounding Box), Score addieren -
            # beide Hinweise (Raster + Beschriftung) bestaetigen sich gegenseitig.
            x0 = min(overlap.rel_x, cand.rel_x)
            y0 = min(overlap.rel_y, cand.rel_y)
            x1 = max(overlap.rel_x + overlap.rel_w, cand.rel_x + cand.rel_w)
            y1 = max(overlap.rel_y + overlap.rel_h, cand.rel_y + cand.rel_h)
            overlap.rel_x, overlap.rel_y = x0, y0
            overlap.rel_w, overlap.rel_h = x1 - x0, y1 - y0
            overlap.score = min(1.0, overlap.score + cand.score * 0.3)
            overlap.method = "grid+label_density" if overlap.method != cand.method else overlap.method
    return merged


def find_titleblock_candidates(
    image: Image.Image, label_synonyms: list[str], max_candidates: int = 3
) -> list[RegionCandidate]:
    """Liefert bis zu `max_candidates` bewertete Kandidatenbereiche (rel.
    Koordinaten 0..1 bezogen auf `image`, bereits aufgerichtet)."""
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)

    grid_candidates = _grid_candidates(gray)
    label_candidates = _label_density_candidates(image, label_synonyms)

    all_candidates = _merge_overlapping(grid_candidates + label_candidates)

    if not all_candidates:
        return [
            RegionCandidate(
                rel_x=0.0, rel_y=0.0, rel_w=1.0, rel_h=1.0,
                score=0.15, method="fallback_full_page",
            )
        ]

    all_candidates.sort(key=lambda c: c.score, reverse=True)
    return all_candidates[:max_candidates]
