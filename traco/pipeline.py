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
QUALITY = {"fast": 1, "balanced": 2, "best": 4}


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
    timings: dict = field(default_factory=dict)

    def report(self) -> dict:
        return {
            "tipo": self.kind,
            "quality": {
                k: v for k, v in self.metrics.items() if k not in ("ssim", "delta_e")
            },
            "timings": self.timings,
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
        base = [dict(speckle=0), dict(speckle=1), dict(speckle=2), dict(speckle=3)]
    elif kind in ("logo", "illustration"):
        base = [
            dict(sigma=0.45, length=3.5),
            dict(sigma=1.2, length=6.0),
            dict(sigma=0.45, length=4.5),
            dict(sigma=0.0, length=3.5),
        ]
    else:
        base = [
            dict(layer=16, prec=8, speckle=4),
            dict(layer=24, prec=8, speckle=6),
            dict(layer=10, prec=8, speckle=3),
            dict(layer=32, prec=8, speckle=8),
        ]
    return base[:n]


def _trace_lineart(rgba, f, bg, transparent, c):
    work = pre.upscale(rgba, f)
    work = pre.denoise(work, "light")
    mask, ink = pre.binarize(work)
    # VTracer binário lê transparente como preto → entrega tinta preta sobre branco opaco
    canvas = np.full_like(mask, 255)
    canvas[mask[..., 3] > 0, :3] = 0
    params = dict(trace.PRESETS["lineart"], filter_speckle=round(c["speckle"] * f))
    paths = post.parse_paths(trace.vtrace(canvas, params))
    paths = post.recolor(paths, _hex(ink))
    pre_body = "" if (transparent or bg is None) else _bg_rect(bg)
    return paths, pre_body, [ink]


def _prepare_color(rgba, f, kind, colors):
    # Palette and detail geometry are shared across candidates.
    protected = pre.fine_detail_mask(rgba)
    protected = np.repeat(np.repeat(protected, f, axis=0), f, axis=1)
    work = pre.binarize_alpha(pre.upscale(pre.denoise(rgba, "light"), f))
    work, palette = pre.quantize(
        work,
        max_colors=colors or (24 if kind == "logo" else 32),
        merge_delta_e=2.0 if colors else (10.0 if kind == "logo" else 7.0),
    )
    return work, palette, protected, {}


def _trace_color(rgba, f, kind, c, prepared):
    quantized, palette, protected, cache = prepared
    sigma = c["sigma"] * f
    if sigma not in cache:
        work = pre.smooth_labels(quantized, sigma=sigma)
        # A smooth icon must not erase letter stems, counters, punctuation or accents.
        work[protected] = quantized[protected]
        cache[sigma] = work
    params = dict(
        trace.PRESETS[kind],
        filter_speckle=max(1, f),
        length_threshold=c["length"],
        path_precision=1 if f >= 2 else 2,
    )
    paths = post.parse_paths(trace.vtrace(cache[sigma], params))
    return paths, "", palette


def _trace_photo(rgba, f, c):
    work = pre.upscale(rgba, f)
    work = pre.denoise(work, "light")
    work = pre.binarize_alpha(work)
    params = dict(
        trace.PRESETS["photo"],
        layer_difference=c["layer"],
        color_precision=c["prec"],
        filter_speckle=round(c["speckle"] * f),
    )
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
    if colors is not None and (
        isinstance(colors, bool) or not isinstance(colors, int) or not 2 <= colors <= 64
    ):
        raise InputError("O número de cores deve ser um inteiro entre 2 e 64.")
    transparent = transparent or remove_bg_ai
    t0 = time.perf_counter()
    times = {"prepare": 0.0, "trace": 0.0, "evaluate": 0.0}
    rgba, meta = load_image(source)
    a: Analysis = analyze(rgba, meta["has_alpha"])
    kind = a.kind if preset == "auto" else preset
    H, W = rgba.shape[:2]
    out_w, out_h = meta["original_size"]
    if colors is not None and kind not in ("logo", "illustration"):
        raise InputError(
            "--cores exige preset logo ou illustration; use -p illustration para posterizar fotos."
        )

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
        return Result(
            svg,
            kind,
            m,
            body.count("<path"),
            analysis={**a.to_dict(), **meta},
            seconds=time.perf_counter() - t0,
        )

    # amplia imagens pequenas (curvas precisam de pixels para ficarem suaves)
    # (foto não amplia: só multiplicaria caminhos; traço segue o mkbitmap: no máx. 2-3x)
    target = {"lineart": 1000, "logo": 1200, "illustration": 1200, "photo": 0}[kind]
    f = pre.pick_upscale(W, H, target=target, max_factor=3) if target else 1

    reference = evaluate.Reference(rgba)
    prepared = None
    if kind in ("logo", "illustration"):
        start = time.perf_counter()
        prepared = _prepare_color(rgba, f, kind, colors)
        times["prepare"] += time.perf_counter() - start
    tried, best = [], None
    stop_reason = "budget"
    for index, c in enumerate(_candidates(kind, QUALITY[quality], colors)):
        start = time.perf_counter()
        if kind == "lineart":
            paths, pre_body, palette = _trace_lineart(rgba, f, bg, transparent, c)
        elif kind == "photo":
            paths, pre_body, palette = _trace_photo(rgba, f, c)
        else:
            paths, pre_body, palette = _trace_color(rgba, f, kind, c, prepared)
        svg = post.build_svg(
            paths, W * f, H * f, out_w, out_h, precision=1 if f >= 2 else 2, title=title
        )
        if pre_body:
            svg = (
                svg.replace(">", ">" + pre_body, 1)
                if "<title>" not in svg
                else svg.replace("</title>", "</title>" + pre_body, 1)
            )
        times["trace"] += time.perf_counter() - start
        start = time.perf_counter()
        m = evaluate.compare(rgba, svg, reference=reference)
        value = evaluate.score(m, len(paths), kind, len(svg.encode()))
        times["evaluate"] += time.perf_counter() - start
        gain = value - best[0] if best is not None else float("inf")
        tried.append({**c, **m, "caminhos": len(paths), "score": round(value, 4)})
        if best is None or value > best[0]:
            best = (value, svg, m, len(paths), palette)
        # best extends the balanced search only while there is meaningful progress.
        if (
            quality == "best"
            and index >= 1
            and (gain < 0.003 or best[2]["quality_score"] >= 0.97)
        ):
            stop_reason = "plateau" if gain < 0.003 else "target"
            break

    # A conservative binary classification still gets a color fallback if validation fails.
    if preset == "auto" and kind == "lineart" and best[2]["status"] != "ok":
        start = time.perf_counter()
        prepared = _prepare_color(rgba, f, "logo", colors)
        times["prepare"] += time.perf_counter() - start
        start = time.perf_counter()
        paths, _, palette = _trace_color(
            rgba, f, "logo", dict(sigma=0.45, length=3.5), prepared
        )
        svg = post.build_svg(
            paths, W * f, H * f, out_w, out_h, precision=1 if f >= 2 else 2, title=title
        )
        times["trace"] += time.perf_counter() - start
        start = time.perf_counter()
        m = evaluate.compare(rgba, svg, reference=reference)
        value = evaluate.score(m, len(paths), "logo", len(svg.encode()))
        times["evaluate"] += time.perf_counter() - start
        tried.append(
            {"fallback": "logo", **m, "caminhos": len(paths), "score": round(value, 4)}
        )
        if value > best[0]:
            best = (value, svg, m, len(paths), palette)
            kind = "logo"
            a.notes.append("Saída binária reprovada; usado candidato colorido.")
    _, svg, m, n, palette = best
    if optimize:
        svg = post.svgo(svg)
        m = evaluate.compare(rgba, svg, reference=reference)
        n = svg.count("<path")
    return Result(
        svg,
        kind,
        m,
        n,
        palette=palette,
        candidates=tried,
        analysis={**a.to_dict(), **meta, "upscale": f, "stop_reason": stop_reason},
        seconds=time.perf_counter() - t0,
        timings={k: round(v, 4) for k, v in times.items()},
    )
