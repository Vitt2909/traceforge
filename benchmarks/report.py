"""Build original/before/after contact sheets and a self-contained HTML report."""

from pathlib import Path
import argparse
import base64
import csv
import html
import json
import statistics
from PIL import Image, ImageDraw, ImageFont

p = argparse.ArgumentParser()
p.add_argument("--inputs", type=Path, required=True)
p.add_argument("--measurements", type=Path, required=True)
p.add_argument("-o", "--output", type=Path, required=True)
a = p.parse_args()
out = a.output
out.mkdir(parents=True, exist_ok=True)
sets = {
    key: json.loads((a.measurements / key / "summary.json").read_text())
    for key in ["before-balanced", "after-balanced", "before-best", "after-best"]
}
lookup = {key: {r["image"]: r for r in values} for key, values in sets.items()}
labels = {
    "01_sabor_arte": "Sabor & Arte",
    "02_forcefit": "ForceFit",
    "03_livia_barros": "Lívia Barros",
    "04_mundopet": "MundoPet",
    "05_techfix": "TechFix",
    "06_nova_era": "Nova Era",
    "07_horizonte": "Horizonte",
    "08_grao_prosa": "Grão & Prosa",
    "09_donna": "Donna",
    "10_rapidcar": "RapidCar",
    "grid": "Grade inteira",
}
columns = [
    "image",
    "quality",
    "version",
    "seconds",
    "kb",
    "ssim",
    "delta_e",
    "peak_rss_mb",
    "paths",
]
with (out / "metrics.csv").open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for version, rows in sets.items():
        for row in rows:
            writer.writerow(
                {
                    **{k: row[k] for k in columns if k != "version"},
                    "version": version.split("-")[0],
                }
            )
(out / "metrics.json").write_text(json.dumps(sets, indent=2) + "\n")
font = ImageFont.load_default(size=18)
blocks = []
sheets = []
for source in sorted(a.inputs.glob("*.png")):
    name = source.stem
    paths = [
        source,
        a.measurements / "before-balanced" / name / "run-1.png",
        a.measurements / "after-balanced" / name / "run-1.png",
    ]
    ims = [Image.open(path).convert("RGB") for path in paths]
    w, h = ims[0].size
    canvas = Image.new("RGB", (3 * w + 32, h + 66), "#edf0f4")
    draw = ImageDraw.Draw(canvas)
    for i, (im, label) in enumerate(
        zip(ims, ["Original", "Antes · balanced", "Depois · balanced"])
    ):
        x = 8 + i * (w + 8)
        draw.text((x, 10), label, font=font, fill="#182330")
        canvas.paste(im, (x, 42))
    sheet = out / (name + ".png")
    canvas.save(sheet)
    sheets.append(sheet)
    b = lookup["before-balanced"][source.name]
    c = lookup["after-balanced"][source.name]
    img = base64.b64encode(sheet.read_bytes()).decode()
    blocks.append(
        f'<section><h2>{html.escape(labels[name])}</h2><p>{b["seconds"]:.2f} → {c["seconds"]:.2f} s · {b["kb"]:.1f} → {c["kb"]:.1f} KB · SSIM {b["ssim"]:.4f} → {c["ssim"]:.4f} · ΔE {b["delta_e"]:.2f} → {c["delta_e"]:.2f} · RAM {b["peak_rss_mb"]:.1f} → {c["peak_rss_mb"]:.1f} MB</p><div class="image"><img src="data:image/png;base64,{img}" alt="{html.escape(labels[name])}: original, antes, depois" loading="lazy"></div></section>'
    )
rows = []
for source in sorted(lookup["before-balanced"]):
    b = lookup["before-balanced"][source]
    c = lookup["after-balanced"][source]
    rows.append(
        f"| {labels[Path(source).stem]} | {b['seconds']:.2f} → {c['seconds']:.2f} | {b['kb']:.1f} → {c['kb']:.1f} | {b['ssim']:.4f} → {c['ssim']:.4f} | {b['delta_e']:.2f} → {c['delta_e']:.2f} | {b['peak_rss_mb']:.1f} → {c['peak_rss_mb']:.1f} |"
    )
method = """Medições na mesma máquina Linux/Python 3.12, duas execuções em processos separados por entrada e qualidade. Tempo: mediana do tempo de conversão, sem importação/instalação nem renderização das pranchas. RAM: pico RSS do processo, incluindo imports, obtido por getrusage; não é memória incremental da função. KB = 1024 bytes. Recortes em grade 5×2, margem interna de 3 px, sem redimensionar. SHA-256 da grade: 9d57d03ee7627ba9bf75833092de1234a101af8ea18c33b1be36591f96b35dbd. Baseline: commit 1cb321a79c89f713366d4b676e762339073001c7. O script de benchmark foi adicionado nesta correção e é idêntico antes/depois."""
notes = """O Nova Era perdeu o dourado no baseline. O RapidCar ficou no limite da classificação antiga (saturação média 0,10027; corte em 0,10), mas não virou lineart nestes recortes nem no ZIP sem margem. A falha do retângulo preto foi reproduzida forçando o caminho lineart e coberta por regressões de polaridade, cor e validação. Não se apresenta esse caso forçado como resultado automático medido na tabela. SSIM global pode cair quando texturas do fundo são simplificadas, mesmo com letras preservadas; a nova nota combina bordas, componentes pequenos e fidelidade de cor. Ela não certifica reconhecimento de texto/OCR. SVGs podem crescer para representar os detalhes que antes eram apagados. Horizonte contém fotografia e mantém o aviso de revisão dos detalhes."""
aggregate = []
for group in ("Média dos 10 logos", "Grade inteira"):
    for quality in ("balanced", "best"):
        selected = {}
        for version in ("before", "after"):
            selected[version] = [
                r
                for r in sets[version + "-" + quality]
                if (r["image"] == "grid.png") == (group == "Grade inteira")
            ]
        means = {
            v: {
                k: statistics.mean(r[k] for r in values)
                for k in ["seconds", "kb", "ssim", "delta_e", "peak_rss_mb"]
            }
            for v, values in selected.items()
        }
        b, c = means["before"], means["after"]
        aggregate.append(
            f"| {group} / {quality} | {b['seconds']:.2f} → {c['seconds']:.2f} | {b['kb']:.1f} → {c['kb']:.1f} | {b['ssim']:.4f} → {c['ssim']:.4f} | {b['delta_e']:.2f} → {c['delta_e']:.2f} | {b['peak_rss_mb']:.1f} → {c['peak_rss_mb']:.1f} |"
        )
quality_note = "No RapidCar forçado para lineart, o baseline produziu fundo preto com SSIM 0,803. O avaliador novo atribui nota 0,0415 e status rejected a esse SVG; a saída automática corrigida recebe 0,8197. Nos 10 logos, best não melhorou a saída sobre balanced, mas seu custo médio adicional caiu de 93% para 9%; a busca parou após 2 candidatos em 8 logos e após 3 em 2 logos."
md = (
    "# Comparação dos 10 logos — antes e depois\n\n"
    + method
    + "\n\n"
    + notes
    + "\n\n"
    + quality_note
    + "\n\n| Conjunto / qualidade | Tempo (s) | KB | SSIM | ΔE76 | Pico RSS (MB) |\n|---|---:|---:|---:|---:|---:|\n"
    + "\n".join(aggregate)
    + "\n\n| Entrada | Tempo (s) | KB | SSIM | ΔE76 | Pico RSS (MB) |\n|---|---:|---:|---:|---:|---:|\n"
    + "\n".join(rows)
    + "\n\n"
)
for name in sorted(labels):
    if name == "grid":
        continue
    md += f"## {labels[name]}\n\n![Original, antes e depois]({name}.png)\n\n"
md += "[Dados brutos: JSON, SVG e renderizações das duas repetições](benchmark-runs.zip). [Métricas CSV](metrics.csv). [Auditoria de qualidade com a mesma métrica nas duas saídas](quality-audit.json).\n"
(out / "README.md").write_text(md)
page = """<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TraceForge — comparação dos 10 logos</title><style>body{margin:0;background:#f3f5f7;color:#182330;font:16px/1.6 system-ui}main{max-width:1120px;margin:auto;padding:32px 20px}h1{font-size:32px;line-height:1.2}section{background:white;border-radius:14px;padding:20px;margin:24px 0;border:1px solid #d8dfe5}.image{overflow:auto}.image img{width:100%;min-width:900px;display:block}p{max-width:1000px}.note{padding:16px;background:#fff1d6;border-radius:10px}details{margin:20px 0}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}td,th{border-bottom:1px solid #d8dfe5;padding:8px;text-align:left}small{color:#566675}</style><main><h1>TraceForge: os 10 logos, antes e depois</h1>"""
page += "<p>" + html.escape(quality_note) + "</p>"
page += (
    "<p>"
    + html.escape(method)
    + "</p><details><summary>Limites e interpretação dos resultados</summary><p>"
    + html.escape(notes)
    + "</p></details>"
)
page += '<div style="overflow:auto"><table><tr><th>Logo</th><th>Tempo s</th><th>KB</th><th>SSIM</th><th>ΔE76</th><th>RAM MB</th></tr>'
for row in aggregate + rows:
    page += (
        "<tr>"
        + "".join(
            "<td>" + html.escape(cell.strip()) + "</td>"
            for cell in row.split("|")[1:-1]
        )
        + "</tr>"
    )
page += "</table></div>" + "".join(blocks) + "</main></html>"
(out / "TraceForge_Comparacao_10_Logos.html").write_text(page)
print(out / "TraceForge_Comparacao_10_Logos.html")
