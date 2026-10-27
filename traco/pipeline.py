"""Orquestração: arquivo entra → engenharia → .svg sai.

    entrada → análise → pré-processamento → traçado (N candidatos)
            → pós-processamento → avaliação → melhor candidato → .svg
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import evaluate, postprocess as post, preprocess as pre, trace
from .analyze import Analysis, analyze
from .ingest import InputError, load_image

KINDS = ("auto", "logo", "lineart", "illustration", "photo", "pixel")
QUALITY = {"fast": 1, "balanced": 3, "best": 6}


@dataclass
class Result:
    svg: str
    kind: str
    metrics: dict
    paths: int
    palette: list = field(default_factory=list)
    candidates: list = field(default_factory=list)
    analysis: dict = field(default_factory=dict)
    seconds: float = 0.0

    def report(self) -> dict:
        return {
            "tipo": self.kind,
            "ssim": self.metrics.get("ssim"),
            "delta_e": self.metrics.get("delta_e"),
            "caminhos": self.paths,
            "bytes": len(self.svg.encode()),
            "paleta": ["#%02X%02X%02X" % c for c in self.palette],
            "candidatos_testados": self.candidates,
            "analise": self.analysis,
            "segundos": round(self.seconds, 2),
        }


def _hex(c) -> str:
    return "#%02X%02X%02X" % tuple(c)


def _bg_rect(color) -> str:
    return f'<rect width="100%" height="100%" fill="{_hex(color)}"/>'


# ----------------------------------------------------------- estratégias ----
def _candidates(kind: str, n: int, colors: int | None) -> list[dict]:
    """Variações de parâmetros testadas sequencialmente; a avaliação escolhe a melhor."""
    if kind == "lineart":
        base = [dict(speckle=2), dict(speckle=4), dict(speckle=1), dict(speckle=6), dict(speckle=3), dict(speckle=8)]
    elif kind == "logo":
        base = [dict(colors=16, de=10.0, speckle=2), dict(colors=12, de=16.0, speckle=2),
                dict(colors=24, de=6.0, speckle=2), dict(colors=8, de=20.0, speckle=3),
                dict(colors=16, de=8.0, speckle=1), dict(colors=32, de=4.0, speckle=1)]
    elif kind == "illustration":
        base = [dict(colors=24, de=7.0, speckle=2, shift=False), dict(colors=16, de=10.0, speckle=3, shift=True),
                dict(colors=32, de=5.0, speckle=2, shift=False), dict(colors=12, de=12.0, speckle=3, shift=True),
                dict(colors=48, de=4.0, speckle=2, shift=False), dict(colors=8, de=16.0, speckle=4, shift=True)]
    elif kind == "photo":
        base = [dict(layer=16, prec=8, speckle=4), dict(layer=24, prec=8, speckle=6), dict(layer=10, prec=8, speckle=3),
                dict(layer=32, prec=8, speckle=8), dict(layer=8, prec=7, speckle=4), dict(layer=48, prec=8, speckle=10)]
    else:
        base = [{}]
    if colors:  # usuário fixou nº de cores → varia só o resto
        for b in base:
            if "colors" in b:
                b["colors"], b["de"] = colors, 2.0
    return base[:n]


def _trace_lineart(rgba, f, bg, transparent, c):
    work = pre.upscale(rgba, f)
    work = pre.denoise(work, "light")
    mask, ink = pre.binarize(work)
    # VTracer binário lê transparente como preto → entrega tinta preta sobre branco opaco
    canvas = np.full_like(mask, 255)
    canvas[mask[..., 3] > 0, :3] = 0
    params = dict(trace.PRESETS["lineart"], filter_speckle=max(2, round(c["speckle"] * f)))
    paths = post.parse_paths(trace.vtrace(canvas, params))
    paths = post.recolor(paths, _hex(ink))
    pre_body = "" if (transparent or bg is None) else _bg_rect(bg)
    return paths, pre_body, [ink]


def _trace_color(rgba, f, kind, c):
    work = pre.upscale(rgba, f)
    work = pre.denoise(work, "light" if kind == "logo" else "medium")
    if c.get("shift"):
        work = pre.posterize_meanshift(work, sp=6 * f // 2 + 4, sr=20)
    work = pre.binarize_alpha(work)
    work, palette = pre.quantize(work, max_colors=c["colors"], merge_delta_e=c["de"])
    work = pre.clean_label_speckles(work, min_area=max(4, int(c["speckle"] ** 2 * f * f)))
    # bordas lisas = menos nós (logo pode suavizar mais: formas geométricas)
    work = pre.smooth_labels(work, sigma=(1.5 if kind == "logo" else 0.8) * f)
    params = dict(trace.PRESETS[kind], filter_speckle=max(2, round(c["speckle"] * f)),
                  length_threshold=10.0, path_precision=1 if f >= 2 else 2)
    paths = post.parse_paths(trace.vtrace(work, params))
    return paths, "", palette


def _trace_photo(rgba, f, c):
    work = pre.upscale(rgba, f)
    work = pre.denoise(work, "light")
    work = pre.binarize_alpha(work)
    params = dict(trace.PRESETS["photo"], layer_difference=c["layer"], color_precision=c["prec"],
                  filter_speckle=max(2, round(c["speckle"] * f)))
    paths = post.parse_paths(trace.vtrace(work, params))
    return paths, "", []


# ------------------------------------------------------------- principal ----
def vectorize(
    source: str | Path | bytes,
    preset: str = "auto",
    quality: str = "balanced",
    colors: int | None = None,
    transparent: bool = False,
    remove_bg_ai: bool = False,
    optimize: bool = False,
    title: str | None = None,
) -> Result:
    if preset not in KINDS:
        raise InputError(f"Preset inválido: {preset}")
    if quality not in QUALITY:
        raise InputError(f"Qualidade inválida: {quality}")
    if colors is not None and (isinstance(colors, bool) or not isinstance(colors, int) or not 2 <= colors <= 64):
        raise InputError("O número de cores deve ser um inteiro entre 2 e 64.")
    transparent = transparent or remove_bg_ai
    t0 = time.time()
    rgba, meta = load_image(source)
    a: Analysis = analyze(rgba, meta["has_alpha"])
    kind = a.kind if preset == "auto" else preset
    H, W = rgba.shape[:2]
    out_w, out_h = meta["original_size"]
    if colors is not None and kind not in ("logo", "illustration"):
        raise InputError("--cores exige preset logo ou illustration; use -p illustration para posterizar fotos.")

    # fundo
    bg = a.background
    if transparent:
        if remove_bg_ai:
            rgba = pre.remove_background_ai(rgba)
        elif bg is not None:
            rgba = pre.remove_flat_background(rgba, bg)

    # pixel art: caminho exato, sem candidatos
    if kind == "pixel":
        body, nw, nh = trace.pixel_art_svg(rgba, a.pixel_scale)
        svg = post.build_svg(body, nw, nh, out_w, out_h, title=title, crisp=True)
        if optimize:
            svg = post.svgo(svg)
        m = evaluate.compare(rgba, svg)
        return Result(svg, kind, m, body.count("<path"), analysis={**a.to_dict(), **meta}, seconds=time.time() - t0)

    # amplia imagens pequenas (curvas precisam de pixels para ficarem suaves)
    # (foto não amplia: só multiplicaria caminhos; traço segue o mkbitmap: no máx. 2-3x)
    target = {"lineart": 1000, "logo": 1200, "illustration": 1200, "photo": 0}[kind]
    f = pre.pick_upscale(W, H, target=target, max_factor=3) if target else 1

    tried, best = [], None
    for c in _candidates(kind, QUALITY[quality], colors):
        if kind == "lineart":
            paths, pre_body, palette = _trace_lineart(rgba, f, bg, transparent, c)
        elif kind == "photo":
            paths, pre_body, palette = _trace_photo(rgba, f, c)
        else:
            paths, pre_body, palette = _trace_color(rgba, f, kind, c)

        svg = post.build_svg(paths, W * f, H * f, out_w, out_h, precision=1 if f >= 2 else 2, title=title)
        if pre_body:
            svg = svg.replace(">", ">" + pre_body, 1) if "<title>" not in svg else svg.replace("</title>", "</title>" + pre_body, 1)
        m = evaluate.compare(rgba, svg)
        s = evaluate.score(m, len(paths), kind, len(svg.encode()))
        tried.append({**c, **m, "caminhos": len(paths), "score": round(s, 4)})
        if best is None or s > best[0]:
            best = (s, svg, m, len(paths), palette)

    _, svg, m, n, palette = best
    if optimize:
        svg = post.svgo(svg)
        m = evaluate.compare(rgba, svg)
        n = svg.count("<path")
    return Result(svg, kind, m, n, palette=palette, candidates=tried,
                  analysis={**a.to_dict(), **meta, "upscale": f}, seconds=time.time() - t0)
