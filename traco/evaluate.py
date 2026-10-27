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

        png = cairosvg.svg2png(bytestring=svg.encode(), output_width=width, output_height=height)
    im = Image.open(io.BytesIO(png)).convert("RGBA")
    if im.size != (width, height):
        im = im.resize((width, height), Image.LANCZOS)
    return np.asarray(im)


def _on_white(rgba: np.ndarray) -> np.ndarray:
    a = rgba[..., 3:4].astype(np.float32) / 255
    return (rgba[..., :3].astype(np.float32) * a + 255 * (1 - a)).astype(np.uint8)


def compare(original: np.ndarray, svg: str, max_side: int = 768) -> dict:
    h, w = original.shape[:2]
    s = min(1.0, max_side / max(w, h))
    W, H = max(1, round(w * s)), max(1, round(h * s))
    ref = np.asarray(Image.fromarray(original).resize((W, H), Image.LANCZOS))
    got = rasterize(svg, W, H)
    a, b = _on_white(ref), _on_white(got)
    # SSIM requires an odd window >= 3. Pad tiny images by extending edges.
    pad_h, pad_w = max(0, 3 - H), max(0, 3 - W)
    aa = np.pad(a, ((0, pad_h), (0, pad_w), (0, 0)), mode="edge")
    bb = np.pad(b, ((0, pad_h), (0, pad_w), (0, 0)), mode="edge")
    window = min(7, aa.shape[0], aa.shape[1])
    window -= 1 - window % 2
    ssim = structural_similarity(aa, bb, channel_axis=2, data_range=255, win_size=window)
    la = cv2.cvtColor(a.astype(np.float32) / 255, cv2.COLOR_RGB2LAB)
    lb = cv2.cvtColor(b.astype(np.float32) / 255, cv2.COLOR_RGB2LAB)
    de = float(np.linalg.norm(la - lb, axis=2).mean())
    return {"ssim": round(float(ssim), 4), "delta_e": round(de, 2)}


def score(metrics: dict, paths: int, kind: str, nbytes: int = 0) -> float:
    """Maior é melhor: fidelidade (SSIM, ΔE) menos uma penalidade leve de complexidade.

    Logos/traços pagam mais caro por complexidade (devem ser simples e editáveis);
    fotos pagam menos (fidelidade importa mais que tamanho).
    """
    wp, wb = {"logo": (0.010, 0.010), "lineart": (0.008, 0.008), "illustration": (0.006, 0.005),
              "photo": (0.003, 0.002)}.get(kind, (0.006, 0.005))
    kb = nbytes / 1024
    return metrics["ssim"] - 0.004 * metrics["delta_e"] - wp * math.log2(max(paths, 1)) - wb * math.log2(kb + 1)
