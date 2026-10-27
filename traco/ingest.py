"""Etapa 1 — Entrada: abre qualquer imagem e normaliza para RGBA (numpy)."""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

SUPPORTED = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".avif", ".heic"}
MAX_PIXELS = 20_000_000
MAX_BYTES = 20 * 1024 * 1024
MAX_SIDE = 4096  # proteção contra imagens gigantes num serviço público


class InputError(ValueError):
    pass


def load_image(source: str | Path | bytes) -> tuple[np.ndarray, dict]:
    """Retorna (rgba uint8 HxWx4, metadados)."""
    if isinstance(source, (bytes, bytearray)):
        data = bytes(source)
        name = "upload"
    else:
        path = Path(source)
        if not path.exists():
            raise InputError(f"Arquivo não encontrado: {path}")
        if path.suffix.lower() == ".svg":
            raise InputError("O arquivo já é SVG — nada a vetorizar.")
        if path.stat().st_size > MAX_BYTES:
            raise InputError("Arquivo maior que 20 MB.")
        data = path.read_bytes()
        name = path.name

    if len(data) > MAX_BYTES:
        raise InputError("Arquivo maior que 20 MB.")
    try:
        im = Image.open(io.BytesIO(data))
        if im.width * im.height > MAX_PIXELS:
            raise InputError("Imagem excede o limite de 20 megapixels.")
        image_format = im.format
        im.seek(0)  # GIF/WebP animado: usa o primeiro quadro
        im = ImageOps.exif_transpose(im)  # foto de celular "deitada"
    except InputError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise InputError("Não consegui ler a imagem — formato não suportado ou arquivo corrompido.") from exc

    meta = {"name": name, "format": image_format, "mode": im.mode, "original_size": im.size}

    if im.mode in ("P", "LA", "L", "1", "CMYK", "I;16", "I", "F"):
        im = im.convert("RGBA")
    elif im.mode != "RGBA":
        im = im.convert("RGBA")

    w, h = im.size
    if max(w, h) > MAX_SIDE:
        scale = MAX_SIDE / max(w, h)
        im = im.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
        meta["downscaled_to"] = im.size

    rgba = np.asarray(im, dtype=np.uint8).copy()
    meta["has_alpha"] = bool((rgba[..., 3] < 250).any())
    return rgba, meta
