import io
import threading
import time
import xml.etree.ElementTree as ET

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from traceforge import vectorize
from traco import vectorize as legacy_vectorize
from traco.cli import main
from traco.evaluate import rasterize
from traco.ingest import InputError, load_image
from traco.web import app


def png(image):
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


@pytest.mark.parametrize("size", [(1, 1), (1, 12), (2, 2), (6, 4)])
def test_tiny_images(size):
    result = vectorize(png(Image.new("RGBA", size, (30, 60, 90, 128))), preset="pixel")
    assert result.metrics["ssim"] > .99
    rendered = rasterize(result.svg, *size)
    assert np.max(np.abs(rendered[..., 3].astype(int) - 128)) <= 1


def test_blank_transparency():
    result = vectorize(png(Image.new("RGBA", (32, 32), (0, 0, 0, 0))), preset="logo", quality="fast")
    assert not rasterize(result.svg, 32, 32)[..., 3].any()


def test_rgba_grid_does_not_discard_alpha_changes():
    pixels = np.zeros((16, 16, 4), dtype=np.uint8)
    pixels[..., :3] = [220, 50, 30]
    pixels[..., 3] = np.arange(16, dtype=np.uint8)[None, :] * 17
    result = vectorize(png(Image.fromarray(pixels)), preset="pixel")
    rendered = rasterize(result.svg, 16, 16)
    assert np.max(np.abs(rendered[..., 3].astype(int) - pixels[..., 3])) <= 1


@pytest.mark.parametrize("kwargs", [{"preset":"invalid"}, {"quality":"invalid"}, {"colors":0}, {"colors":65}, {"colors":2.5}, {"colors":True}, {"preset":"photo", "colors":4}])
def test_invalid_options(kwargs):
    with pytest.raises(InputError):
        vectorize(png(Image.new("RGB", (8, 8), "red")), **kwargs)


def test_oversized_dimensions_rejected_before_decode(monkeypatch):
    monkeypatch.setattr("traco.ingest.MAX_PIXELS", 100)
    with pytest.raises(InputError, match="megapixels"):
        load_image(png(Image.new("RGB", (11, 10))))


def test_downscaled_image_keeps_output_dimensions(monkeypatch):
    monkeypatch.setattr("traco.ingest.MAX_SIDE", 32)
    result = vectorize(png(Image.new("RGB", (80, 40), "red")), preset="pixel")
    root = ET.fromstring(result.svg)
    assert (root.attrib["width"], root.attrib["height"]) == ("80", "40")
    assert result.analysis["format"] == "PNG"


def test_alias():
    assert vectorize is legacy_vectorize


def test_cli_directory_and_report(tmp_path):
    source=tmp_path / "input.png"
    source.write_bytes(png(Image.new("RGB", (16, 16), "blue")))
    assert main([str(source), "-o", str(tmp_path / "nested" / "out"), "--relatorio"]) == 0
    assert (tmp_path / "nested/out/input.svg").exists()
    assert (tmp_path / "nested/out/input.json").exists()


def test_cli_batch_glob(tmp_path):
    for name in ("a", "b"):
        (tmp_path / f"{name}.png").write_bytes(png(Image.new("RGB", (8, 8), "red")))
    assert main([str(tmp_path / "*.png"), "-o", str(tmp_path / "out")]) == 0
    assert len(list((tmp_path / "out").glob("*.svg"))) == 2


def test_cli_missing_file(tmp_path, capsys):
    assert main([str(tmp_path / "missing.png")]) == 1
    assert "Arquivo não encontrado" in capsys.readouterr().err


def test_cli_duplicate_destinations(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main([str(tmp_path / "a/input.png"), str(tmp_path / "b/input.png"), "-o", str(tmp_path / "out")])
    assert exc.value.code == 2


def test_web_home_health_and_unicode_download():
    with TestClient(app) as client:
        assert "TraceForge" in client.get("/").text
        assert client.get("/healthz").json()["status"] == "ok"
        response = client.post("/api/vetorizar", files={"arquivo": ("ação-日本.png", png(Image.new("RGB", (8, 8), "red")), "image/png")})
        assert response.status_code == 200, response.text
        assert "filename*=UTF-8''" in response.headers["content-disposition"]
        ET.fromstring(response.text)
        assert response.headers["X-TraceForge-Report"]


@pytest.mark.parametrize("data", [{"cores":0}, {"cores":65}, {"preset":"bad"}, {"qualidade":"bad"}])
def test_web_invalid_options(data):
    with TestClient(app) as client:
        response = client.post("/api/vetorizar", data=data, files={"arquivo": ("a.png", b"bad")})
        assert response.status_code == 400


def test_web_invalid_and_oversized(monkeypatch):
    with TestClient(app) as client:
        assert client.post("/api/vetorizar", files={"arquivo": ("bad.png", b"bad")}).status_code == 400
        monkeypatch.setattr("traco.web.MAX_BYTES", 10)
        assert client.post("/api/vetorizar", files={"arquivo": ("big.png", b"a" * 11)}).status_code == 413


def test_web_busy_does_not_block_health(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    real = vectorize
    def slow(*args, **kwargs):
        entered.set()
        assert release.wait(10)
        return real(*args, **kwargs)
    monkeypatch.setattr("traco.web.vectorize", slow)
    data = png(Image.new("RGB", (8, 8), "red"))
    results = []
    with TestClient(app) as client:
        worker = threading.Thread(target=lambda: results.append(client.post("/api/vetorizar", files={"arquivo": ("a.png", data)})))
        worker.start()
        try:
            assert entered.wait(10)
            assert client.get("/healthz").status_code == 200
            assert client.post("/api/vetorizar", files={"arquivo": ("b.png", data)}).status_code == 503
        finally:
            release.set()
            worker.join(10)
        assert results[0].status_code == 200
