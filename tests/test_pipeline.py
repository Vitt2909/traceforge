"""Testes de fumaça: cada tipo de imagem entra e sai um SVG válido e fiel."""
import io
import xml.etree.ElementTree as ET

import numpy as np
import pytest
from PIL import Image, ImageDraw

from traco import vectorize
from traco.ingest import InputError


def _png(im: Image.Image, fmt: str = "PNG", **kw) -> bytes:
    b = io.BytesIO()
    im.save(b, fmt, **kw)
    return b.getvalue()


def _logo() -> bytes:
    im = Image.new("RGB", (300, 180), "white")
    d = ImageDraw.Draw(im)
    d.ellipse((10, 10, 170, 170), fill=(230, 80, 40))
    d.ellipse((50, 50, 130, 130), fill="white")
    d.rounded_rectangle((185, 40, 290, 140), radius=20, fill=(30, 60, 140))
    return _png(im, "JPEG", quality=70)


def _valid(svg: str) -> ET.Element:
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")
    assert root.get("viewBox")
    return root


def test_logo_vira_poucas_formas():
    r = vectorize(_logo(), quality="fast")
    _valid(r.svg)
    assert r.kind == "logo"
    assert r.metrics["ssim"] > 0.88
    assert r.paths <= 12
    assert len(r.svg) < 20_000


def test_pixel_art_exato():
    rng = np.random.default_rng(0)
    pal = np.array([[0, 0, 0], [255, 255, 255], [220, 40, 60]], np.uint8)
    spr = Image.fromarray(pal[rng.integers(0, 3, (12, 12))]).resize((96, 96), Image.NEAREST)
    r = vectorize(_png(spr))
    _valid(r.svg)
    assert r.kind == "pixel"
    assert r.metrics["ssim"] > 0.99
    assert 'shape-rendering="crispEdges"' in r.svg


def test_lineart_preto_e_branco():
    im = Image.new("L", (400, 160), 255)
    ImageDraw.Draw(im).line([(20, 80), (120, 20), (220, 140), (380, 40)], fill=0, width=6)
    r = vectorize(_png(im))
    _valid(r.svg)
    assert r.kind == "lineart"
    assert r.metrics["ssim"] > 0.95


def test_fundo_transparente():
    r = vectorize(_logo(), quality="fast", transparent=True)
    from traco.evaluate import rasterize

    a = rasterize(r.svg, 300, 180)
    assert a[2, 2, 3] == 0          # canto: fundo removido
    assert a[90, 90, 3] == 255      # miolo branco do anel (não conectado à borda) fica


def test_tamanho_original_preservado():
    r = vectorize(_logo(), quality="fast")
    root = _valid(r.svg)
    assert root.get("width") == "300" and root.get("height") == "180"


def test_entrada_invalida():
    with pytest.raises(InputError):
        vectorize(b"isto nao e uma imagem")
