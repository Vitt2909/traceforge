"""Reproducible subprocess benchmark; same harness for baseline and candidate.

python benchmarks/bench.py logos/*.png -r 2 --sem-extras --salvar-svg
Use --repo to compare a frozen checkout without changing the harness.
"""

from __future__ import annotations
import argparse
import glob
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys


def worker(args):
    import time

    sys.path.insert(0, str(Path(args.repo).resolve()))
    from traco import vectorize
    from traco.evaluate import rasterize
    from PIL import Image

    start = time.perf_counter()
    result = vectorize(args.inputs[0], quality=args.qualidade)
    elapsed = time.perf_counter() - start
    if os.name == "nt":
        import psutil

        memory = psutil.Process().memory_info()
        peak = getattr(memory, "peak_wset", memory.rss)
    else:
        import resource

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform != "darwin":
            peak *= 1024
    report = result.report()
    report.update(seconds_wall=elapsed, peak_rss_mb=peak / 1024**2)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix(".json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    if args.salvar_svg:
        output.with_suffix(".svg").write_text(result.svg, encoding="utf-8")
        w, h = Image.open(args.inputs[0]).size
        Image.fromarray(rasterize(result.svg, w, h)).save(output.with_suffix(".png"))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("inputs", nargs="+")
    p.add_argument("-r", "--repeticoes", type=int, default=2)
    p.add_argument(
        "-q", "--qualidade", choices=["fast", "balanced", "best"], default="balanced"
    )
    p.add_argument(
        "--sem-extras",
        action="store_true",
        help="Não roda motores externos; benchmark nativo apenas",
    )
    p.add_argument("--salvar-svg", action="store_true")
    p.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    p.add_argument("-o", "--output", default="benchmark-results")
    p.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = p.parse_args()
    if args.worker:
        worker(args)
        return
    if args.repeticoes < 1:
        p.error("-r deve ser >= 1")
    inputs = sorted(
        {
            str(Path(f).resolve())
            for pat in args.inputs
            for f in (glob.glob(pat) or [pat])
        }
    )
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    # Fix BLAS thread settings equally for both versions; OpenCV untouched.
    env.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    rows = []
    for source in inputs:
        runs = []
        for repeat in range(args.repeticoes):
            dest = output / Path(source).stem / f"run-{repeat + 1}"
            cmd = [
                sys.executable,
                str(Path(__file__).resolve()),
                source,
                "--worker",
                "--repo",
                str(Path(args.repo).resolve()),
                "-q",
                args.qualidade,
                "-o",
                str(dest),
            ]
            if args.salvar_svg:
                cmd.append("--salvar-svg")
            subprocess.run(cmd, check=True, env=env)
            runs.append(json.loads(dest.with_suffix(".json").read_text()))
        row = dict(
            image=Path(source).name,
            quality=args.qualidade,
            kind=runs[0]["tipo"],
            seconds=statistics.median(r["seconds_wall"] for r in runs),
            kb=statistics.median(r["bytes"] / 1024 for r in runs),
            ssim=statistics.median(r["ssim"] for r in runs),
            delta_e=statistics.median(r["delta_e"] for r in runs),
            peak_rss_mb=max(r["peak_rss_mb"] for r in runs),
            paths=statistics.median(r["caminhos"] for r in runs),
            repetitions=args.repeticoes,
        )
        if "quality" in runs[0]:
            row["quality_score"] = statistics.median(
                r["quality"].get("quality_score", 0) for r in runs
            )
            row["detail_recall"] = statistics.median(
                r["quality"].get("detail_recall", 0) for r in runs
            )
            row["status"] = runs[0]["quality"].get("status")
        rows.append(row)
        (output / "summary.json").write_text(json.dumps(rows, indent=2) + "\n")
        print(
            f"{row['image']}: {row['kind']} {row['seconds']:.2f}s {row['kb']:.1f}KB SSIM={row['ssim']:.4f} dE={row['delta_e']:.2f} RSS={row['peak_rss_mb']:.1f}MB",
            flush=True,
        )


if __name__ == "__main__":
    main()
