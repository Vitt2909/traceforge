"""TraceForge command line, with legacy traco entry points."""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

from .ingest import InputError
from .pipeline import KINDS, QUALITY, vectorize


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="traceforge", description="Transforma imagens em SVG."
    )
    p.add_argument("--version", action="version", version="TraceForge 0.1.1")
    p.add_argument("entrada", nargs="+", help='imagens ou padrão, ex.: "pasta/*.png"')
    p.add_argument("-o", "--saida", help="arquivo .svg ou pasta")
    p.add_argument("-p", "--preset", choices=KINDS, default="auto")
    p.add_argument("-q", "--qualidade", choices=list(QUALITY), default="balanced")
    p.add_argument(
        "-c",
        "--cores",
        type=int,
        help="máximo de cores, 2–64; presets logo/illustration",
    )
    p.add_argument(
        "-t", "--transparente", action="store_true", help="remove fundo chapado"
    )
    p.add_argument(
        "--ia-fundo", action="store_true", help="remove fundo com IA (extra ai)"
    )
    p.add_argument(
        "--otimizar", action="store_true", help="SVGO opcional (requer Node.js)"
    )
    p.add_argument("--relatorio", action="store_true", help="salva métricas em JSON")
    args = p.parse_args(argv)
    if args.cores is not None and not 2 <= args.cores <= 64:
        p.error("--cores deve estar entre 2 e 64")
    sources = list(
        dict.fromkeys(
            path
            for pattern in args.entrada
            for path in (glob.glob(pattern) or [pattern])
        )
    )
    output = Path(args.saida) if args.saida else None
    many = len(sources) > 1
    if many and output and output.suffix.lower() == ".svg" and not output.is_dir():
        p.error("para várias entradas, --saida deve ser uma pasta")
    is_dir = output and (many or output.is_dir() or output.suffix.lower() != ".svg")
    destinations = []
    for src in sources:
        source = Path(src)
        dest = (
            output / (source.stem + ".svg")
            if is_dir
            else (output or source.with_suffix(".svg"))
        )
        if dest.resolve() == source.resolve():
            p.error("a saída não pode sobrescrever a imagem de entrada")
        destinations.append(dest)
    if len({d.resolve() for d in destinations}) != len(destinations):
        p.error(
            "entradas com o mesmo nome gerariam a mesma saída; use pastas separadas"
        )
    code = 0
    for src, dst in zip(sources, destinations):
        try:
            r = vectorize(
                src,
                preset=args.preset,
                quality=args.qualidade,
                colors=args.cores,
                transparent=args.transparente,
                remove_bg_ai=args.ia_fundo,
                optimize=args.otimizar,
                title=Path(src).stem,
            )
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(r.svg, encoding="utf-8")
            rep = r.report()
            if args.relatorio:
                dst.with_suffix(".json").write_text(
                    json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            status = r.metrics.get("status", "review")
            prefix = (
                "OK"
                if status == "ok"
                else ("REJEITADO" if status == "rejected" else "REVISAR")
            )
            if status == "rejected":
                code = 2
            for warning in r.metrics.get("warnings", []):
                print(f"Aviso: {src}: {warning}", file=sys.stderr)
            print(
                f"{prefix} {src} -> {dst} [{r.kind}] qualidade={r.metrics.get('quality_score', 0):.3f} SSIM={rep['ssim']} "
                f"caminhos={rep['caminhos']} {rep['bytes'] / 1024:.1f} KB {rep['segundos']}s"
            )
        except (InputError, RuntimeError, OSError) as exc:
            print(f"Erro: {src}: {exc}", file=sys.stderr)
            code = 1
    return code


if __name__ == "__main__":
    raise SystemExit(main())
