"""Etapa 4 — Traçado: transforma pixels em caminhos.

Motor principal: VTracer (Rust, MIT, cor + preto-e-branco, hierárquico "stacked",
sem buracos entre camadas). Pixel art usa um conversor próprio que gera
retângulos exatos — curvas estragam pixel art.
"""
from __future__ import annotations

import cv2
import numpy as np
import vtracer

# Parâmetros do VTracer por tipo de imagem.
# filter_speckle: descarta manchas menores que N px (no tamanho já ampliado)
# color_precision: bits significativos por canal (8 = não reagrupa nossa paleta)
# layer_difference: diferença mínima de cor entre camadas
# corner_threshold: ângulo (graus) acima do qual vira canto, não curva
# length_threshold: comprimento mínimo de segmento antes de suavizar
# splice_threshold: ângulo para emendar curvas spline
PRESETS: dict[str, dict] = {
    "lineart": dict(colormode="binary", mode="spline", filter_speckle=6, corner_threshold=60,
                    length_threshold=4.0, splice_threshold=45, max_iterations=10, path_precision=2),
    "logo": dict(colormode="color", hierarchical="stacked", mode="spline", filter_speckle=6,
                 color_precision=8, layer_difference=4, corner_threshold=60, length_threshold=4.0,
                 splice_threshold=45, max_iterations=10, path_precision=2),
    "illustration": dict(colormode="color", hierarchical="stacked", mode="spline", filter_speckle=8,
                         color_precision=8, layer_difference=4, corner_threshold=60, length_threshold=4.0,
                         splice_threshold=45, max_iterations=10, path_precision=2),
    "photo": dict(colormode="color", hierarchical="stacked", mode="spline", filter_speckle=4,
                  color_precision=6, layer_difference=16, corner_threshold=60, length_threshold=4.0,
                  splice_threshold=45, max_iterations=10, path_precision=1),
}


def vtrace(rgba: np.ndarray, params: dict) -> str:
    """Chama o VTracer com PNG em memória (bem mais rápido que lista de pixels)."""
    ok, buf = cv2.imencode(".png", cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA))
    if not ok:
        raise RuntimeError("falha ao codificar PNG intermediário")
    return vtracer.convert_raw_image_to_svg(buf.tobytes(), img_format="png", **params)


def pixel_art_svg(rgba: np.ndarray, scale: int) -> tuple[str, int, int]:
    """Pixel art → SVG exato: reduz à grade nativa e une pixels em retângulos por cor.

    Retorna (svg_body_paths, largura_nativa, altura_nativa).
    """
    if scale > 1:
        rgba = rgba[scale // 2::scale, scale // 2::scale]
    h, w = rgba.shape[:2]
    alpha_ok = rgba[..., 3] > 0
    key = (rgba[..., 0].astype(np.int64) << 16) | (rgba[..., 1].astype(np.int64) << 8) | rgba[..., 2]
    key = (key << 8) | rgba[..., 3].astype(np.int64)
    key[~alpha_ok] = -1

    by_color: dict[int, list[str]] = {}
    used = np.zeros((h, w), dtype=bool)
    for y in range(h):
        x = 0
        while x < w:
            c = key[y, x]
            if c < 0 or used[y, x]:
                x += 1
                continue
            # estende para a direita
            x2 = x
            while x2 + 1 < w and key[y, x2 + 1] == c and not used[y, x2 + 1]:
                x2 += 1
            # estende para baixo enquanto a faixa inteira for da mesma cor
            y2 = y
            while y2 + 1 < h and np.all(key[y2 + 1, x:x2 + 1] == c) and not used[y2 + 1, x:x2 + 1].any():
                y2 += 1
            used[y:y2 + 1, x:x2 + 1] = True
            by_color.setdefault(int(c), []).append(f"M{x} {y}h{x2 - x + 1}v{y2 - y + 1}h-{x2 - x + 1}z")
            x = x2 + 1

    body = "".join(
        f'<path fill="#{c >> 8:06X}" fill-opacity="{(c & 255) / 255:.8f}" d="{"".join(rects)}"/>' for c, rects in by_color.items()
    )
    return body, w, h
