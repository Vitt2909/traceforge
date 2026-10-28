"""Regressions against the supplied logos and independent pixel-level checks."""

import io
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw

from traco import vectorize
from traco.evaluate import compare, rasterize

GRID = Path(__file__).parent / "fixtures/logo-grid.png"
NAMES = [
    "sabor_arte",
    "forcefit",
    "livia_barros",
    "mundopet",
    "techfix",
    "nova_era",
    "horizonte",
    "grao_prosa",
    "donna",
    "rapidcar",
]


def crop(index, inset=3):
    grid = Image.open(GRID).convert("RGBA")
    w, h = grid.size
    row, col = divmod(index, 5)
    return grid.crop(
        (
            round(col * w / 5) + inset,
            round(row * h / 2) + inset,
            round((col + 1) * w / 5) - inset,
            round((row + 1) * h / 2) - inset,
        )
    )


def data(image):
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


@pytest.fixture(scope="module")
def logos():
    results = {}
    for index, name in enumerate(NAMES):
        original = crop(index)
        result = vectorize(data(original))
        rendered = Image.fromarray(rasterize(result.svg, *original.size))
        results[name] = (original, result, rendered)
    return results


@pytest.mark.parametrize("name", ["rapidcar", "nova_era"])
def test_colored_logos_not_binary(logos, name):
    original, result, rendered = logos[name]
    assert result.kind in ("logo", "illustration")
    assert result.metrics["ssim"] > 0.88
    # Brand chroma must survive, independently of the classification/report.
    a = np.asarray(original)[..., :3].astype(float)
    b = np.asarray(rendered)[..., :3].astype(float)
    chromatic = (a.max(2) - a.min(2) > 45) & (a.max(2) > 80)
    assert chromatic.sum() > 300
    assert (b.max(2) - b.min(2))[chromatic].mean() > 35


def test_rapidcar_untrimmed():
    image = crop(9, 0)
    result = vectorize(data(image))
    assert result.kind != "lineart"
    assert result.metrics["edge_recall"] > 0.85
    assert result.metrics["status"] != "rejected"


# Slogan/subtitle regions in original crop coordinates; each named region must survive.
TEXT_ROIS = [
    ("sabor_arte", (28, 270, 280, 297)),
    ("sabor_arte", (45, 389, 268, 433)),
    ("forcefit", (42, 326, 265, 349)),
    ("forcefit", (70, 393, 257, 435)),
    ("livia_barros", (20, 319, 286, 341)),
    ("livia_barros", (48, 396, 270, 437)),
    ("techfix", (14, 311, 291, 335)),
    ("techfix", (12, 413, 290, 435)),
    ("grao_prosa", (38, 308, 269, 337)),
    ("grao_prosa", (40, 378, 274, 418)),
    ("rapidcar", (30, 252, 278, 284)),
    ("rapidcar", (24, 339, 285, 381)),
]


@pytest.mark.parametrize("name,box", TEXT_ROIS)
def test_small_text_survives(logos, name, box):
    original, _, rendered = logos[name]
    a = cv2.cvtColor(
        np.asarray(original.crop(box))[..., :3], cv2.COLOR_RGB2GRAY
    ).astype(float)
    b = cv2.cvtColor(
        np.asarray(rendered.crop(box))[..., :3], cv2.COLOR_RGB2GRAY
    ).astype(float)
    # High-pass stroke contrast, with sign: light-on-dark and dark-on-light.
    aa = a - cv2.GaussianBlur(a, (0, 0), 2.0)
    bb = b - cv2.GaussianBlur(b, (0, 0), 2.0)
    stroke = np.abs(aa) > 20
    assert stroke.sum() > 30, "ROI must actually contain lettering"
    retained = (np.abs(bb) > 12) & (np.sign(aa) == np.sign(bb))
    assert retained[stroke].mean() > 0.75, (name, box, retained[stroke].mean())
    assert np.corrcoef(aa[stroke], bb[stroke])[0, 1] > 0.65


def test_blank_svg_is_rejected_even_when_global_ssim_is_high():
    rgba = np.asarray(crop(9, 0))
    h, w = rgba.shape[:2]
    blank = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"><rect width="100%" height="100%" fill="black"/></svg>'
    broken = compare(rgba, blank)
    good = vectorize(data(crop(9, 0)))
    assert broken["ssim"] > 0.7
    assert broken["status"] == "rejected"
    assert broken["edge_recall"] < 0.05
    assert broken["quality_score"] < good.metrics["quality_score"] * 0.4


def test_white_ink_on_dark_background():
    image = Image.new("RGB", (300, 180), "black")
    ImageDraw.Draw(image).line(
        [(20, 110), (80, 40), (160, 130), (280, 35)], fill="white", width=7
    )
    result = vectorize(data(image), preset="lineart")
    pixels = rasterize(result.svg, 300, 180)
    assert pixels[110, 20, :3].mean() > 150
    assert pixels[5, 5, :3].mean() < 20
    assert result.metrics["edge_recall"] > 0.8


def test_auto_binary_failure_retries_color(monkeypatch):
    image = Image.new("RGB", (300, 180), "black")
    ImageDraw.Draw(image).ellipse((50, 30, 250, 150), fill="white")
    monkeypatch.setattr(
        "traco.pipeline._trace_lineart",
        lambda *args: (
            [],
            '<rect width="100%" height="100%" fill="#000000"/>',
            [(0, 0, 0)],
        ),
    )
    result = vectorize(data(image))
    assert result.kind == "logo"
    assert result.metrics["edge_recall"] > 0.8
    assert any(c.get("fallback") == "logo" for c in result.candidates)


def test_palette_is_prepared_once_for_best(monkeypatch):
    from traco import preprocess

    calls = []
    original = preprocess.quantize

    def counted(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(preprocess, "quantize", counted)
    result = vectorize(data(crop(0)), quality="best")
    assert len(calls) == 1
    assert 2 <= len(result.candidates) <= 4


def test_best_stops_on_plateau_and_keeps_balanced(monkeypatch):
    monkeypatch.setattr("traco.evaluate.score", lambda *args: 0.8)
    result = vectorize(data(crop(0)), quality="best")
    assert len(result.candidates) == 2
    assert result.analysis["stop_reason"] == "plateau"


def test_cli_reports_rejected_conversion(monkeypatch, tmp_path, capsys):
    from traco.pipeline import Result
    from traco.cli import main

    r = Result(
        "<svg/>",
        "logo",
        {
            "ssim": 0.8,
            "delta_e": 3,
            "quality_score": 0.16,
            "status": "rejected",
            "warnings": ["Perda grave de detalhes."],
        },
        0,
    )
    monkeypatch.setattr("traco.cli.vectorize", lambda *a, **kw: r)
    assert main(["input.png", "-o", str(tmp_path / "output.svg")]) == 2
    captured = capsys.readouterr()
    assert "REJEITADO" in captured.out
    assert "OK" not in captured.out
    assert "Perda grave" in captured.err


def test_clean_jpeg_geometry_is_not_falsely_rejected():
    image = Image.new("RGB", (300, 180), "white")
    draw = ImageDraw.Draw(image)
    draw.ellipse((10, 10, 170, 170), fill=(230, 80, 40))
    draw.ellipse((50, 50, 130, 130), fill="white")
    draw.rounded_rectangle((185, 40, 290, 140), radius=20, fill=(30, 60, 140))
    stream = io.BytesIO()
    image.save(stream, format="JPEG", quality=70)
    result = vectorize(stream.getvalue(), quality="fast")
    assert result.metrics["status"] == "ok"
    assert result.metrics["quality_score"] > 0.8
