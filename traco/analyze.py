"""Etapa 2 — Análise: descobre que tipo de imagem é para escolher a estratégia.

Classes:
  pixel        pixel art (grade nítida, poucas cores) → retângulos exatos
  lineart      preto-e-branco / traço / assinatura    → traçado binário
  logo         cores chapadas, poucas cores           → quantização + traçado colorido
  illustration ilustração/personagem/flat com sombras → posterização + traçado colorido
  photo        foto, gradientes, muitas cores         → traçado fino (arquivo grande)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from PIL import Image


@dataclass
class Analysis:
    kind: str
    width: int
    height: int
    has_alpha: bool
    pixel_scale: int = 1  # fator de ampliação detectado em pixel art
    distinct_colors: int = 0  # cores distintas (4 bits/canal)
    top16_coverage: float = 0.0  # fração dos pixels cobertos pelas 16 cores mais comuns
    top64_coverage: float = 0.0
    saturation: float = 0.0
    chromatic_fraction: float = 0.0
    extremes_ratio: float = 0.0  # fração de pixels muito claros ou muito escuros
    background: tuple[int, int, int] | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


def _opaque_rgb(rgba: np.ndarray) -> np.ndarray:
    mask = rgba[..., 3] >= 128
    return rgba[..., :3][mask]


def detect_pixel_scale(rgba: np.ndarray) -> int:
    """Se a imagem é pixel art ampliada por vizinho-mais-próximo, devolve o fator (>=2)."""
    rgb = rgba.astype(np.int16)
    h, w = rgb.shape[:2]
    if min(h, w) < 8:
        return 1
    # posições onde a cor muda na horizontal e na vertical
    dx = np.any(np.abs(np.diff(rgb, axis=1)) > 8, axis=2)  # (h, w-1)
    dy = np.any(np.abs(np.diff(rgb, axis=0)) > 8, axis=2)  # (h-1, w)
    cols = np.nonzero(dx.any(axis=0))[0] + 1
    rows = np.nonzero(dy.any(axis=1))[0] + 1
    if len(cols) < 2 or len(rows) < 2:
        return 1
    g = int(np.gcd.reduce(np.concatenate([cols, rows])))
    if g < 2 or w % g or h % g:
        return 1
    # Only collapse a grid when every RGBA sample in every cell is identical.
    native = rgba[::g, ::g]
    rebuilt = np.repeat(np.repeat(native, g, axis=0), g, axis=1)
    return g if np.array_equal(rebuilt, rgba) else 1


def detect_background(rgba: np.ndarray, tol: int = 18) -> tuple[int, int, int] | None:
    """Fundo = cor dos 4 cantos, se os cantos concordam e são opacos."""
    h, w = rgba.shape[:2]
    k = max(1, min(h, w) // 50)
    patches = [rgba[:k, :k], rgba[:k, -k:], rgba[-k:, :k], rgba[-k:, -k:]]
    if any((p[..., 3] < 250).any() for p in patches):
        return None
    means = np.array([p[..., :3].reshape(-1, 3).mean(axis=0) for p in patches])
    if np.ptp(means, axis=0).max() > tol:
        return None
    return tuple(int(v) for v in means.mean(axis=0))


def analyze(rgba: np.ndarray, has_alpha: bool) -> Analysis:
    h, w = rgba.shape[:2]
    a = Analysis(kind="photo", width=w, height=h, has_alpha=has_alpha)
    a.background = detect_background(rgba)

    # amostra reduzida para estatística rápida
    small = Image.fromarray(rgba).copy()
    small.thumbnail((256, 256), Image.NEAREST)
    s = np.asarray(small).copy()
    # tira ruído de JPEG antes de contar cores (senão todo logo em JPEG parece "foto")
    import cv2

    s[..., :3] = cv2.bilateralFilter(s[..., :3], 5, 40, 5)
    rgb = _opaque_rgb(s)
    if rgb.size == 0:
        a.kind = "logo"
        a.notes.append("imagem quase toda transparente")
        return a

    q = (rgb >> 4).astype(np.int32)
    keys = (q[:, 0] << 8) | (q[:, 1] << 4) | q[:, 2]
    _, counts = np.unique(keys, return_counts=True)
    counts = np.sort(counts)[::-1]
    total = counts.sum()
    a.distinct_colors = int(len(counts))
    a.top16_coverage = float(counts[:16].sum() / total)
    a.top64_coverage = float(counts[:64].sum() / total)

    hsv = np.asarray(Image.fromarray(rgb.reshape(-1, 1, 3)).convert("HSV")).reshape(
        -1, 3
    )
    a.saturation = float(hsv[:, 1].mean() / 255)
    # A white/black background must not dilute a small but meaningful brand color.
    chromatic = (
        (rgb.max(axis=1).astype(int) - rgb.min(axis=1) > 24)
        & (hsv[:, 1] > 55)
        & (hsv[:, 2] > 40)
    )
    a.chromatic_fraction = float(chromatic.mean())
    monochrome = np.count_nonzero(chromatic) < max(8, len(rgb) * 0.001)
    gray = rgb.mean(axis=1)
    a.extremes_ratio = float(((gray < 70) | (gray > 190)).mean())

    a.pixel_scale = detect_pixel_scale(rgba)
    native_w, native_h = w // a.pixel_scale, h // a.pixel_scale

    if (
        (a.pixel_scale >= 2 or max(w, h) <= 128)
        and max(native_w, native_h) <= 256
        and a.distinct_colors <= 256
        and a.top64_coverage > 0.97
    ):
        a.kind = "pixel"
    elif monochrome and a.saturation < 0.10 and a.extremes_ratio > 0.90:
        a.kind = "lineart"
    elif a.top16_coverage > 0.93:
        a.kind = "logo"
    elif a.top16_coverage > 0.70 and a.top64_coverage > 0.92:
        a.kind = "illustration"
    else:
        a.kind = "photo"
        a.notes.append(
            "foto/gradiente: o SVG vai ficar pesado; considere --preset illustration para um visual pôster"
        )
    return a
