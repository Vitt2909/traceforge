"""Etapa 3 — Pré-processamento: é aqui que a qualidade é decidida.

Regra de ouro (repetida em todo fórum de design): o traçador só é tão bom quanto
a imagem que recebe. Então limpamos ruído, ampliamos imagens pequenas,
reduzimos a paleta para as cores "de verdade" e binarizamos o alfa.
"""

from __future__ import annotations

import cv2
import numpy as np


# ---------------------------------------------------------------- fundo ----
def remove_flat_background(
    rgba: np.ndarray, bg: tuple[int, int, int], tol: float = 12.0
) -> np.ndarray:
    """Torna transparente o fundo chapado conectado às bordas (flood fill).

    Só remove regiões ligadas à borda, então o branco *dentro* do logo fica.
    """
    out = rgba.copy()
    lab = cv2.cvtColor(rgba[..., :3].astype(np.float32) / 255.0, cv2.COLOR_RGB2LAB)
    bg_lab = cv2.cvtColor(np.float32([[bg]]) / 255.0, cv2.COLOR_RGB2LAB)[0, 0]
    near = (np.linalg.norm(lab - bg_lab, axis=2) < tol).astype(np.uint8)
    n, labels = cv2.connectedComponents(near, connectivity=4)
    border = np.unique(
        np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]])
    )
    border = border[border != 0]
    mask = np.isin(labels, border)
    out[mask, 3] = 0
    return out


def remove_background_ai(rgba: np.ndarray) -> np.ndarray:
    """Remoção de fundo com IA (rembg/U²-Net/BiRefNet) — dependência opcional."""
    try:
        from rembg import remove  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Instale o extra de IA: python -m pip install '.[ai]'"
        ) from exc
    from PIL import Image

    return np.asarray(remove(Image.fromarray(rgba)).convert("RGBA"))


# ------------------------------------------------------------- tamanho ----
def upscale(rgba: np.ndarray, factor: int) -> np.ndarray:
    if factor <= 1:
        return rgba
    h, w = rgba.shape[:2]
    # premultiplica o alfa para não criar halo escuro nas bordas
    a = rgba[..., 3:4].astype(np.float32) / 255.0
    rgb = rgba[..., :3].astype(np.float32) * a
    rgb = cv2.resize(rgb, (w * factor, h * factor), interpolation=cv2.INTER_CUBIC)
    a2 = cv2.resize(a[..., 0], (w * factor, h * factor), interpolation=cv2.INTER_CUBIC)[
        ..., None
    ]
    a2 = np.clip(a2, 0, 1)
    rgb = np.where(a2 > 1e-3, rgb / np.maximum(a2, 1e-3), 0)
    out = np.dstack([np.clip(rgb, 0, 255), a2 * 255]).astype(np.uint8)
    return out


def pick_upscale(
    width: int, height: int, target: int = 1600, max_factor: int = 4
) -> int:
    """Amplia imagens pequenas para que curvas tenham "pixels suficientes" para ficarem suaves."""
    side = max(width, height)
    f = 1
    while side * (f + 1) <= target and f < max_factor:
        f += 1
    return f


# --------------------------------------------------------------- ruído ----
def denoise(rgba: np.ndarray, strength: str = "light") -> np.ndarray:
    """Bilateral suaviza ruído/artefato de JPEG preservando bordas."""
    out = rgba.copy()
    d, sc, ss = {"light": (5, 30, 5), "medium": (7, 50, 7), "strong": (9, 75, 9)}[
        strength
    ]
    out[..., :3] = cv2.bilateralFilter(rgba[..., :3], d, sc, ss)
    return out


def posterize_meanshift(rgba: np.ndarray, sp: int = 8, sr: int = 24) -> np.ndarray:
    """Mean-shift achata texturas em regiões de cor (bom para ilustração/foto→pôster)."""
    out = rgba.copy()
    out[..., :3] = cv2.pyrMeanShiftFiltering(rgba[..., :3], sp, sr)
    return out


def binarize_alpha(rgba: np.ndarray, thr: int = 128) -> np.ndarray:
    out = rgba.copy()
    out[..., 3] = np.where(rgba[..., 3] >= thr, 255, 0).astype(np.uint8)
    out[out[..., 3] == 0, :3] = 0
    return out


# --------------------------------------------------------- quantização ----
def quantize(
    rgba: np.ndarray,
    max_colors: int = 16,
    merge_delta_e: float = 6.0,
    min_share: float = 0.0015,
    seed: int = 7,
    edge_aware: bool = True,
) -> tuple[np.ndarray, list[tuple[int, int, int]]]:
    """K-means no espaço LAB (perceptual) + fusão de cores quase iguais.

    Devolve a imagem com cada pixel opaco "encaixado" na paleta e a paleta final.
    O número de cores é automático: começa em `max_colors` e funde clusters com
    ΔE < `merge_delta_e`; clusters minúsculos (< min_share) são reabsorvidos.

    edge_aware: a paleta é aprendida só com pixels de regiões "planas". Pixels de
    borda (antialiasing, halo de JPEG) são cores de transição que não existem no
    desenho — se entrassem no k-means virariam anéis finos com centenas de caminhos.
    Eles são depois encaixados na cor real mais próxima.
    """
    from scipy.spatial import cKDTree

    opaque = rgba[..., 3] > 0
    if not opaque.any():
        return rgba.copy(), []
    # Fit at most 12k pixels once. Iterative refinement is bounded
    # by sample count, not the number of pixels in the source image.
    rgb = rgba[..., :3][opaque]
    rng = np.random.default_rng(seed)
    sample_ids = rng.choice(len(rgb), min(len(rgb), 12000), replace=False)
    sample_rgb = rgb[sample_ids]
    sample = cv2.cvtColor(
        sample_rgb.reshape(-1, 1, 3).astype(np.float32) / 255, cv2.COLOR_RGB2LAB
    ).reshape(-1, 3)
    fit = sample
    if edge_aware:
        gray = cv2.cvtColor(rgba[..., :3], cv2.COLOR_RGB2GRAY).astype(np.float32)
        grad = cv2.magnitude(
            cv2.Sobel(gray, cv2.CV_32F, 1, 0), cv2.Sobel(gray, cv2.CV_32F, 0, 1)
        )
        flat = (cv2.dilate(grad, np.ones((3, 3), np.uint8)) < 40)[opaque][sample_ids]
        if flat.mean() > 0.2:
            fit = sample[flat]
    sample = np.ascontiguousarray(fit, dtype=np.float32)
    unique = np.unique(np.round(sample).astype(np.int32), axis=0)
    k = min(max_colors, len(unique), len(sample))
    cv2.setRNGSeed(seed)
    if k == 1:
        centers = sample.mean(axis=0, keepdims=True)
    else:
        _, _, centers = cv2.kmeans(
            sample,
            k,
            None,
            (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5),
            1,
            cv2.KMEANS_PP_CENTERS,
        )
    C = np.asarray(centers, dtype=np.float32)
    for _ in range(5):
        changed = False
        while len(C) > 1:
            distance = np.linalg.norm(C[:, None] - C[None], axis=2)
            np.fill_diagonal(distance, np.inf)
            i, j = np.unravel_index(distance.argmin(), distance.shape)
            if distance[i, j] >= merge_delta_e:
                break
            C[i] = (C[i] + C[j]) / 2
            C = np.delete(C, j, axis=0)
            changed = True
        labels = cKDTree(C).query(sample)[1]
        counts = np.bincount(labels, minlength=len(C))
        keep = counts >= max(1, min_share * len(sample))
        if not keep.any():
            keep[counts.argmax()] = True
        new = np.array(
            [sample[labels == i].mean(axis=0) for i in np.flatnonzero(keep)],
            dtype=np.float32,
        )
        if not changed and len(new) == len(C) and np.abs(new - C).max() < 0.05:
            C = new
            break
        C = new
    palette = cv2.cvtColor(C.reshape(-1, 1, 3), cv2.COLOR_LAB2RGB).reshape(-1, 3)
    palette = np.clip(np.round(palette * 255), 0, 255).astype(np.uint8)
    out = rgba.copy()
    tree = cKDTree(C)
    mapped = np.empty_like(rgb)
    for i in range(0, len(rgb), 65536):
        lab = cv2.cvtColor(
            rgb[i : i + 65536].reshape(-1, 1, 3).astype(np.float32) / 255,
            cv2.COLOR_RGB2LAB,
        ).reshape(-1, 3)
        mapped[i : i + 65536] = palette[tree.query(lab)[1]]
    out[..., :3][opaque] = mapped
    return out, [tuple(int(v) for v in c) for c in palette]


def fine_detail_mask(rgba: np.ndarray) -> np.ndarray:
    """Local bright/dark strokes <= ~8px, including letters and diacritics.

    Contrast threshold suppresses low-amplitude JPEG/texture noise. This detects
    geometry, not text semantics; it never invents or replaces characters.
    """
    alpha = rgba[..., 3:4].astype(np.float32) / 255
    rgb = (rgba[..., :3] * alpha + 255 * (1 - alpha)).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    # Color channels also detect strokes with similar luminance to the background.
    bright = cv2.morphologyEx(rgb, cv2.MORPH_TOPHAT, kernel).max(axis=2)
    dark = cv2.morphologyEx(rgb, cv2.MORPH_BLACKHAT, kernel).max(axis=2)
    mask = (np.maximum(bright, dark) >= 24).astype(np.uint8)
    return cv2.dilate(mask, np.ones((3, 3), np.uint8)).astype(bool)


def clean_label_speckles(rgba: np.ndarray, min_area: int) -> np.ndarray:
    """Remove "manchinhas" (ilhas de cor menores que min_area px) trocando pela cor vizinha dominante."""
    if min_area <= 1:
        return rgba
    out = rgba.copy()
    key = (
        (out[..., 0].astype(np.int32) << 16)
        | (out[..., 1].astype(np.int32) << 8)
        | out[..., 2]
    )
    key[out[..., 3] == 0] = -1
    for color in np.unique(key):
        m = (key == color).astype(np.uint8)
        n, lab, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=4)
        small = np.nonzero(stats[1:, cv2.CC_STAT_AREA] < min_area)[0] + 1
        if len(small) == 0:
            continue
        smask = np.isin(lab, small)
        # dilata para achar a cor vizinha mais comum
        ring = (
            cv2.dilate(smask.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
            & ~smask
        )
        if not ring.any():
            continue
        vals, cnt = np.unique(key[ring], return_counts=True)
        fill = vals[cnt.argmax()]
        key[smask] = fill
    out[..., 3] = np.where(key < 0, 0, 255).astype(np.uint8)
    kk = np.maximum(key, 0)
    out[..., 0] = (kk >> 16) & 255
    out[..., 1] = (kk >> 8) & 255
    out[..., 2] = kk & 255
    return out


# ---------------------------------------------------------- binarização ----
def binarize(rgba: np.ndarray) -> tuple[np.ndarray, tuple[int, int, int]]:
    """Otsu sobre cinza (compondo no branco). Devolve máscara RGBA preta e a cor de tinta real."""
    a = rgba[..., 3:4].astype(np.float32) / 255
    comp = (rgba[..., :3].astype(np.float32) * a + 255 * (1 - a)).astype(np.uint8)
    gray = cv2.cvtColor(comp, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    border = np.concatenate([gray[0], gray[-1], gray[:, 0], gray[:, -1]])
    polarity = cv2.THRESH_BINARY if np.median(border) < 128 else cv2.THRESH_BINARY_INV
    _, ink = cv2.threshold(gray, 0, 255, polarity + cv2.THRESH_OTSU)
    inkmask = ink > 0
    color = (
        tuple(int(v) for v in np.median(comp[inkmask], axis=0))
        if inkmask.any()
        else (0, 0, 0)
    )
    out = np.zeros_like(rgba)
    out[..., 3] = 0
    out[inkmask] = (0, 0, 0, 255)
    return out, color


def smooth_labels(rgba: np.ndarray, sigma: float) -> np.ndarray:
    """Suaviza as fronteiras entre cores já quantizadas sem criar cores novas.

    Cada cor vira uma máscara, cada máscara é borrada (Gaussiana) e cada pixel
    fica com a cor de maior "voto". Remove o serrilhado/artefato de JPEG que
    faria o traçador gerar milhares de nós em bordas que deviam ser retas/curvas.
    """
    if sigma <= 0:
        return rgba
    key = (
        (rgba[..., 0].astype(np.int32) << 16)
        | (rgba[..., 1].astype(np.int32) << 8)
        | rgba[..., 2]
    )
    key[rgba[..., 3] == 0] = -1
    colors = np.unique(key)
    if len(colors) < 2:
        return rgba
    best = np.full(key.shape, -1.0, dtype=np.float32)
    out_key = key.copy()
    k = int(sigma * 3) * 2 + 1
    for c in colors:
        v = cv2.GaussianBlur((key == c).astype(np.float32), (k, k), sigma)
        upd = v > best
        best[upd] = v[upd]
        out_key[upd] = c
    out = np.zeros_like(rgba)
    opaque = out_key >= 0
    kk = np.maximum(out_key, 0)
    out[..., 0] = (kk >> 16) & 255
    out[..., 1] = (kk >> 8) & 255
    out[..., 2] = kk & 255
    out[..., 3] = np.where(opaque, 255, 0)
    return out
