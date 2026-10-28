"""Etapa 6 — Avaliação: rasteriza o SVG e compara com o original.

Métricas:
  ssim        similaridade estrutural (0-1) entre original e SVG renderizado
  delta_e     diferença média de cor percebida (ΔE76; < 2 imperceptível, > 10 visível)
  paths       nº de caminhos (complexidade/editabilidade)
  bytes       tamanho do arquivo
O score usado para escolher entre candidatos equilibra fidelidade e simplicidade.
"""

from __future__ import annotations

import io
import math

import cv2
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity


def rasterize(svg: str, width: int, height: int) -> np.ndarray:
    """SVG → RGBA. Usa resvg (Rust, sem dependência de sistema; funciona no Windows)."""
    try:
        import resvg_py

        png = bytes(resvg_py.svg_to_bytes(svg_string=svg, width=width, height=height))
    except ImportError:  # reserva: cairosvg (exige libcairo instalada)
        import cairosvg

        png = cairosvg.svg2png(
            bytestring=svg.encode(), output_width=width, output_height=height
        )
    im = Image.open(io.BytesIO(png)).convert("RGBA")
    if im.size != (width, height):
        im = im.resize((width, height), Image.LANCZOS)
    return np.asarray(im)


def _on_white(rgba: np.ndarray) -> np.ndarray:
    a = rgba[..., 3:4].astype(np.float32) / 255
    return (rgba[..., :3].astype(np.float32) * a + 255 * (1 - a)).astype(np.uint8)


class Reference:
    """Cache the reference once; retain native-size strokes even on a large sheet."""

    def __init__(self, original: np.ndarray, max_side: int = 768):
        h, w = original.shape[:2]
        s = min(1.0, max_side / max(w, h))
        self.size = (max(1, round(w * s)), max(1, round(h * s)))
        self.rgb = _on_white(
            np.asarray(Image.fromarray(original).resize(self.size, Image.LANCZOS))
        )
        self.lab = cv2.cvtColor(self.rgb.astype(np.float32) / 255, cv2.COLOR_RGB2LAB)
        s = min(1.0, 1536 / max(w, h))
        self.detail_size = (max(1, round(w * s)), max(1, round(h * s)))
        self.detail = _on_white(
            np.asarray(
                Image.fromarray(original).resize(self.detail_size, Image.LANCZOS)
            )
        )
        self.edges = _edges(self.detail)
        self.edge_count = int(self.edges.sum())
        n, labels, stats, _ = cv2.connectedComponentsWithStats(
            self.edges.astype(np.uint8), connectivity=8
        )
        small = (
            (stats[:, cv2.CC_STAT_AREA] >= 8)
            & (stats[:, cv2.CC_STAT_HEIGHT] >= 3)
            & (stats[:, cv2.CC_STAT_WIDTH] >= 2)
            & (stats[:, cv2.CC_STAT_HEIGHT] <= 32)
            & (stats[:, cv2.CC_STAT_WIDTH] <= 160)
        )
        large = (stats[:, cv2.CC_STAT_HEIGHT] > 32) | (
            stats[:, cv2.CC_STAT_WIDTH] > 160
        )
        large[0] = False
        near_large = cv2.dilate(
            large[labels].astype(np.uint8), np.ones((5, 5), np.uint8)
        ).astype(bool)
        near_counts = np.bincount(labels[near_large & self.edges], minlength=n)
        small &= near_counts / np.maximum(stats[:, cv2.CC_STAT_AREA], 1) < 0.2
        small[0] = False
        self.small_ids = np.flatnonzero(small)
        self.labels = labels
        self.counts = stats[:, cv2.CC_STAT_AREA]
        self.chroma = np.linalg.norm(self.lab[..., 1:], axis=2) > 15


def _edges(rgb):
    # Include chromatic boundaries, not just grayscale boundaries.
    rgb = cv2.GaussianBlur(rgb, (3, 3), 0.5)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 40, 100) > 0
    for channel in (0, 1, 2):
        edges |= cv2.Canny(np.ascontiguousarray(rgb[..., channel]), 80, 180) > 0
    return edges


def compare(
    original: np.ndarray,
    svg: str,
    max_side: int = 768,
    reference: Reference | None = None,
) -> dict:
    ref = reference or Reference(original, max_side)
    W, H = ref.size
    a, b = ref.rgb, _on_white(rasterize(svg, W, H))
    pad_h, pad_w = max(0, 3 - H), max(0, 3 - W)
    aa = np.pad(a, ((0, pad_h), (0, pad_w), (0, 0)), mode="edge")
    bb = np.pad(b, ((0, pad_h), (0, pad_w), (0, 0)), mode="edge")
    window = min(7, aa.shape[0], aa.shape[1])
    window -= 1 - window % 2
    ssim = float(
        structural_similarity(aa, bb, channel_axis=2, data_range=255, win_size=window)
    )
    lab = cv2.cvtColor(b.astype(np.float32) / 255, cv2.COLOR_RGB2LAB)
    diff = np.linalg.norm(ref.lab - lab, axis=2)
    de = float(diff.mean())
    color_de = float(diff[ref.chroma].mean()) if ref.chroma.sum() >= 8 else de
    detailed = (
        b
        if ref.detail_size == ref.size
        else _on_white(rasterize(svg, *ref.detail_size))
    )
    got_edges = _edges(detailed)
    near_got = cv2.dilate(got_edges.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(
        bool
    )
    near_ref = cv2.dilate(ref.edges.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(
        bool
    )
    recall = (
        float((ref.edges & near_got).sum() / ref.edge_count) if ref.edge_count else 1.0
    )
    precision = (
        float((got_edges & near_ref).sum() / got_edges.sum())
        if got_edges.any()
        else float(not ref.edge_count)
    )
    f1 = 2 * recall * precision / max(1e-12, recall + precision)
    hits = np.bincount(ref.labels[ref.edges & near_got], minlength=len(ref.counts))
    detail = (
        float(np.mean(hits[ref.small_ids] / ref.counts[ref.small_ids]))
        if len(ref.small_ids)
        else recall
    )
    # Spatial edge matching alone can reward noisy results: balance precision,
    # recall, small components and color fidelity, not white/black background area.
    structure = min(recall, detail)
    fidelity = max(0.0, ssim) * (0.2 + 0.8 * structure) * math.exp(-color_de / 60)
    issues = []
    if ref.edge_count >= 12 and (recall < 0.5 or detail < 0.4):
        status = "rejected"
        issues.append("Perda grave de bordas ou pequenos elementos detectada.")
    elif color_de > 20 or detail < 0.8 or recall < 0.8:
        status = "review"
        issues.append("Revise os detalhes e as cores antes de usar o SVG.")
    else:
        status = "ok"
    return {
        "ssim": round(ssim, 4),
        "delta_e": round(de, 2),
        "edge_recall": round(recall, 4),
        "edge_precision": round(precision, 4),
        "edge_f1": round(f1, 4),
        "detail_recall": round(detail, 4),
        "color_delta_e": round(color_de, 2),
        "quality_score": round(fidelity, 4),
        "status": status,
        "warnings": issues,
    }


def score(metrics: dict, paths: int, kind: str, nbytes: int = 0) -> float:
    """Select on structure and color; size is only a small tie-breaker."""
    value = metrics.get("quality_score", max(0.0, metrics["ssim"]))
    return (
        value
        + 0.12 * metrics.get("edge_f1", 0)
        - 0.002 * metrics["delta_e"]
        - 0.001 * math.log2(max(paths, 1))
        - 0.001 * math.log2(nbytes / 1024 + 1)
    )
