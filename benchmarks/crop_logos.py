"""Crop a 5x2 logo grid with a reproducible 3px inset (no resampling)."""

import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image

p = argparse.ArgumentParser()
p.add_argument("grid")
p.add_argument("-o", "--output", default="logos")
p.add_argument("--inset", type=int, default=3)
a = p.parse_args()
im = Image.open(a.grid).convert("RGB")
w, h = im.size
names = [
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
out = Path(a.output)
out.mkdir(parents=True, exist_ok=True)
manifest = {
    "source_sha256": hashlib.sha256(Path(a.grid).read_bytes()).hexdigest(),
    "size": [w, h],
    "inset": a.inset,
    "crops": [],
}
for i, name in enumerate(names):
    row, col = divmod(i, 5)
    box = (
        round(col * w / 5) + a.inset,
        round(row * h / 2) + a.inset,
        round((col + 1) * w / 5) - a.inset,
        round((row + 1) * h / 2) - a.inset,
    )
    target = out / f"{i + 1:02d}_{name}.png"
    im.crop(box).save(target)
    manifest["crops"].append({"file": target.name, "box": box})
(out / "crops.json").write_text(json.dumps(manifest, indent=2) + "\n")
