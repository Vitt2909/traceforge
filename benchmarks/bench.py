"""Benchmark do TraceForge: tempo (s), memória (MB), tamanho (KB) e qualidade.

Uso:
    python benchmarks/bench.py                       # exemplos/entrada/*, fast/balanced/best
    python benchmarks/bench.py -q balanced -r 5      # só balanced, 5 repetições
    python benchmarks/bench.py img1.png img2.jpg -o resultados/

Cada combinação imagem × qualidade roda num subprocesso limpo, para que o pico
de memória (RSS) de uma conversão não contamine a próxima. Uma execução fria
(imports tardios) é medida à parte; a primeira execução em regime também mede
o tempo por etapa do pipeline.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import platform
import resource
import statistics
import subprocess
import sys
import time
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEPS = ("vtracer", "resvg-py", "opencv-python-headless", "numpy", "Pillow", "scikit-image", "fastapi")
STAGES = {
    "ingestao": [("traco.pipeline", "load_image")],
    "analise": [("traco.pipeline", "analyze")],
    "preprocess": [("traco.preprocess", n) for n in (
        "remove_flat_background", "upscale", "denoise", "posterize_meanshift", "binarize_alpha",
        "quantize", "clean_label_speckles", "binarize", "smooth_labels")],
    "tracado": [("traco.trace", "vtrace"), ("traco.trace", "pixel_art_svg")],
    "postprocess": [("traco.postprocess", n) for n in ("parse_paths", "recolor", "build_svg")],
    "avaliacao": [("traco.evaluate", "compare")],
}


def _maxrss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # Linux: KB


# ------------------------------------------------------------------ worker ----
def _instrument(totals: dict) -> None:
    """Envolve as funções de cada etapa; só a chamada mais externa é contada."""
    import importlib

    depth = [0]
    for stage, targets in STAGES.items():
        for mod_name, fn_name in targets:
            mod = importlib.import_module(mod_name)
            fn = getattr(mod, fn_name)

            def wrapped(*a, _fn=fn, _stage=stage, **kw):
                depth[0] += 1
                t = time.perf_counter()
                try:
                    return _fn(*a, **kw)
                finally:
                    depth[0] -= 1
                    if depth[0] == 0:
                        totals[_stage] = totals.get(_stage, 0.0) + time.perf_counter() - t

            setattr(mod, fn_name, wrapped)


def worker(image: str, quality: str, reps: int) -> dict:
    t = time.perf_counter()
    from traco import vectorize

    import_s = time.perf_counter() - t
    rss_base = _maxrss_mb()

    stages: dict[str, float] = {}
    _instrument(stages)
    t = time.perf_counter()
    vectorize(image, quality=quality)  # execução fria: inclui imports tardios e caches
    cold_s = time.perf_counter() - t
    stages.clear()
    wall, cpu = [], []
    for i in range(reps):
        t, c = time.perf_counter(), time.process_time()
        result = vectorize(image, quality=quality)
        wall.append(time.perf_counter() - t)
        cpu.append(time.process_time() - c)
        if i == 0:
            first_stages = dict(stages)
    rss_peak = _maxrss_mb()

    svg = result.svg.encode()
    rep = result.report()
    return {
        "imagem": Path(image).name,
        "qualidade": quality,
        "tipo": result.kind,
        "entrada_kb": round(Path(image).stat().st_size / 1024, 2),
        "resolucao": "%dx%d" % tuple(result.analysis["original_size"]),
        "svg_kb": round(len(svg) / 1024, 2),
        "svg_gzip_kb": round(len(gzip.compress(svg, 9)) / 1024, 2),
        "caminhos": rep["caminhos"],
        "candidatos": max(1, len(rep["candidatos_testados"])),
        "ssim": rep["ssim"],
        "delta_e": rep["delta_e"],
        "s_mediana": round(statistics.median(wall), 3),
        "s_min": round(min(wall), 3),
        "s_max": round(max(wall), 3),
        "s_fria": round(cold_s, 3),
        "cpu_s_mediana": round(statistics.median(cpu), 3),
        "repeticoes": reps,
        "etapas_s": {k: round(v, 3) for k, v in first_stages.items()},
        "import_s": round(import_s, 3),
        "rss_base_mb": round(rss_base, 1),
        "rss_pico_mb": round(rss_peak, 1),
        "rss_delta_mb": round(rss_peak - rss_base, 1),
    }


# ------------------------------------------------------------------ extras ----
def bench_cli(reps: int = 5) -> dict:
    times = []
    for _ in range(reps):
        t = time.perf_counter()
        subprocess.run([sys.executable, "-m", "traceforge", "--version"], check=True, capture_output=True)
        times.append(time.perf_counter() - t)
    return {"cli_version_s_mediana": round(statistics.median(times), 3)}


def bench_api(image: Path, reps: int = 3) -> dict:
    from fastapi.testclient import TestClient

    from traco.web import app

    data = image.read_bytes()
    with TestClient(app) as client:
        health, conv = [], []
        for _ in range(20):
            t = time.perf_counter()
            client.get("/healthz").raise_for_status()
            health.append(time.perf_counter() - t)
        for _ in range(reps):
            t = time.perf_counter()
            r = client.post("/api/vetorizar", files={"arquivo": (image.name, data)}, data={"qualidade": "balanced"})
            r.raise_for_status()
            conv.append(time.perf_counter() - t)
    return {
        "api_imagem": image.name,
        "healthz_ms_mediana": round(statistics.median(health) * 1000, 2),
        "vetorizar_s_mediana": round(statistics.median(conv), 3),
        "resposta_kb": round(len(r.content) / 1024, 2),
        "cabecalho_relatorio_kb": round(len(r.headers.get("X-TraceForge-Report", "")) / 1024, 2),
    }


def bench_tests() -> dict:
    t = time.perf_counter()
    p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                       cwd=ROOT, capture_output=True, text=True)
    last = (p.stdout.strip().splitlines() or [""])[-1]
    return {"pytest_s": round(time.perf_counter() - t, 2), "pytest_resumo": last, "pytest_ok": p.returncode == 0}


def environment() -> dict:
    deps = {}
    for d in DEPS:
        try:
            deps[d] = metadata.version(d)
        except metadata.PackageNotFoundError:
            pass
    cpu = next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")), platform.processor()) if Path("/proc/cpuinfo").exists() else platform.processor()
    return {"python": platform.python_version(), "platform": f"{platform.system()} {platform.machine()}",
            "cpu": cpu, "nucleos": os.cpu_count(), "dependencies": deps}


# -------------------------------------------------------------- relatório ----
def markdown(data: dict) -> str:
    env = data["environment"]
    out = [f"# Benchmark TraceForge\n",
           f"Python {env['python']} · {env['platform']} · {env['cpu']} ({env['nucleos']} núcleos) · "
           f"{data['repeticoes']} repetições por combinação (mediana)\n",
           "## Conversão por imagem\n",
           "| Imagem | Qualidade | Tipo | Resolução | Entrada KB | SVG KB | SVG gzip KB | Caminhos | Cand. "
           "| SSIM | ΔE | Tempo s (mín–máx) | Fria s | CPU s | Pico RAM MB (+Δ) |",
           "|---|---|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for r in data["resultados"]:
        out.append(f"| {r['imagem']} | {r['qualidade']} | {r['tipo']} | {r['resolucao']} | {r['entrada_kb']} "
                   f"| {r['svg_kb']} | {r['svg_gzip_kb']} | {r['caminhos']} | {r['candidatos']} | {r['ssim']} "
                   f"| {r['delta_e']} | {r['s_mediana']} ({r['s_min']}–{r['s_max']}) | {r['s_fria']} | {r['cpu_s_mediana']} "
                   f"| {r['rss_pico_mb']} (+{r['rss_delta_mb']}) |")
    names = list(STAGES)
    out += ["\n## Tempo por etapa (s, 1ª execução em regime)\n",
            "| Imagem | Qualidade | " + " | ".join(names) + " |",
            "|---|---|" + "--:|" * len(names)]
    for r in data["resultados"]:
        out.append(f"| {r['imagem']} | {r['qualidade']} | "
                   + " | ".join(str(r["etapas_s"].get(n, 0.0)) for n in names) + " |")
    out += ["\n## Totais por qualidade\n", "| Qualidade | Tempo total s | SVG total KB | SSIM médio | ΔE médio |",
            "|---|--:|--:|--:|--:|"]
    for q, s in data["totais"].items():
        out.append(f"| {q} | {s['s']} | {s['svg_kb']} | {s['ssim_medio']} | {s['delta_e_medio']} |")
    if data.get("extras"):
        out += ["\n## Outros\n"] + [f"- **{k}**: {v}" for k, v in data["extras"].items()]
    return "\n".join(out) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("imagens", nargs="*", help="padrão: exemplos/entrada/*")
    p.add_argument("-q", "--qualidade", nargs="+", default=["fast", "balanced", "best"])
    p.add_argument("-r", "--repeticoes", type=int, default=3)
    p.add_argument("-o", "--saida", default=str(ROOT / "benchmarks" / "resultados"))
    p.add_argument("--sem-extras", action="store_true", help="pula CLI, API e pytest")
    p.add_argument("--worker", nargs=3, metavar=("IMG", "Q", "R"), help=argparse.SUPPRESS)
    args = p.parse_args()

    if args.worker:
        img, q, r = args.worker
        print(json.dumps(worker(img, q, int(r))))
        return 0

    images = [Path(i) for i in args.imagens] or sorted((ROOT / "exemplos" / "entrada").iterdir())
    results = []
    for img in images:
        for q in args.qualidade:
            p_ = subprocess.run([sys.executable, __file__, "--worker", str(img), q, str(args.repeticoes)],
                                capture_output=True, text=True)
            if p_.returncode:
                print(f"ERRO {img.name} [{q}]\n{p_.stderr}", file=sys.stderr)
                continue
            r = json.loads(p_.stdout.strip().splitlines()[-1])
            results.append(r)
            print(f"{r['imagem']:<22} {q:<9} {r['tipo']:<8} {r['s_mediana']:>7.3f}s  {r['svg_kb']:>9.2f} KB  "
                  f"SSIM={r['ssim']:<6} ΔE={r['delta_e']:<5} RAM pico={r['rss_pico_mb']} MB", flush=True)

    totals = {}
    for q in args.qualidade:
        rs = [r for r in results if r["qualidade"] == q]
        if rs:
            totals[q] = {"s": round(sum(r["s_mediana"] for r in rs), 2),
                         "svg_kb": round(sum(r["svg_kb"] for r in rs), 1),
                         "ssim_medio": round(statistics.mean(r["ssim"] for r in rs), 4),
                         "delta_e_medio": round(statistics.mean(r["delta_e"] for r in rs), 2)}
    extras = {}
    if not args.sem_extras:
        extras.update(bench_cli())
        extras.update(bench_api(next((i for i in images if "logo" in i.name), images[0])))
        extras.update(bench_tests())
    data = {"environment": environment(), "repeticoes": args.repeticoes, "resultados": results,
            "totais": totals, "extras": extras}

    out = Path(args.saida)
    out.mkdir(parents=True, exist_ok=True)
    (out / "benchmark.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "benchmark.md").write_text(markdown(data), encoding="utf-8")
    print(f"\nSalvo em {out / 'benchmark.json'} e {out / 'benchmark.md'}")
    return 0 if len(results) == len(images) * len(args.qualidade) else 1


if __name__ == "__main__":
    raise SystemExit(main())
