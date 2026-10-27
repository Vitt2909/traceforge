"""Etapa 5 — Pós-processamento: SVG limpo, escalável e editável."""
from __future__ import annotations

import re
import shutil
import subprocess

PATH_RE = re.compile(r'<path d="([^"]*)" fill="(#[0-9A-Fa-f]{6})"(?: transform="translate\(([-\d.]+),([-\d.]+)\)")?\s*/>')
NUM_RE = re.compile(r"-?\d+(?:\.\d+)?(?:e-?\d+)?")


def _fmt(v: float, prec: int) -> str:
    s = f"{v:.{prec}f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _shift_path(d: str, dx: float, dy: float, prec: int) -> str:
    """Aplica translate(dx,dy) direto nas coordenadas (VTracer só usa comandos absolutos M/L/C/Z)."""
    out, idx = [], 0
    for tok in re.findall(r"[MLCZ]|" + NUM_RE.pattern, d):
        if tok in "MLCZ":
            out.append(tok)
            continue
        v = float(tok) + (dx if idx % 2 == 0 else dy)
        idx += 1
        out.append(_fmt(v, prec))
    # junta: letras coladas nos números ("M10 20C...")
    s = " ".join(out)
    s = re.sub(r" ?([MLCZ]) ?", r"\1", s)
    return s


def parse_paths(svg: str) -> list[tuple[str, str]]:
    """Extrai (d, fill) do SVG do VTracer, já com o translate aplicado."""
    paths = []
    for m in PATH_RE.finditer(svg):
        d, fill, tx, ty = m.groups()
        dx, dy = float(tx or 0), float(ty or 0)
        paths.append((d, fill.upper(), dx, dy))
    return paths


def build_svg(
    body_paths: list[tuple[str, str]] | str,
    view_w: int,
    view_h: int,
    out_w: int,
    out_h: int,
    precision: int = 2,
    title: str | None = None,
    crisp: bool = False,
) -> str:
    """Monta o SVG final com viewBox (escala infinita) e tamanho original."""
    if isinstance(body_paths, str):
        body = body_paths
    else:
        parts = []
        last_fill = None
        group_open = False
        for d, fill, dx, dy in body_paths:
            nd = _shift_path(d, dx, dy, precision)
            if not nd or nd == "Z":
                continue
            # agrupa caminhos consecutivos da mesma cor num <g fill> (menor e mais editável)
            if fill != last_fill:
                if group_open:
                    parts.append("</g>")
                parts.append(f'<g fill="{fill}">')
                group_open = True
                last_fill = fill
            parts.append(f'<path d="{nd}"/>')
        if group_open:
            parts.append("</g>")
        body = "".join(parts)

    attrs = [
        'xmlns="http://www.w3.org/2000/svg"',
        f'viewBox="0 0 {view_w} {view_h}"',
        f'width="{out_w}"',
        f'height="{out_h}"',
    ]
    if crisp:
        attrs.append('shape-rendering="crispEdges"')
    t = f"<title>{_escape(title)}</title>" if title else ""
    return f'<svg {" ".join(attrs)}>{t}{body}</svg>\n'


def recolor(paths, color_hex: str):
    return [(d, color_hex, dx, dy) for d, _f, dx, dy in paths]


def svgo(svg: str, timeout: int = 60) -> str:
    """Passa pelo SVGO se o Node estiver disponível (opcional, só encolhe o arquivo)."""
    npx = shutil.which("npx")
    if not npx:
        return svg
    try:
        r = subprocess.run(
            [npx, "--yes", "svgo@3", "-i", "-", "-o", "-", "--multipass"],
            input=svg.encode(), capture_output=True, timeout=timeout, check=True,
        )
        out = r.stdout.decode()
        return out if out.strip().startswith("<svg") else svg
    except Exception:  # noqa: BLE001
        return svg


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
