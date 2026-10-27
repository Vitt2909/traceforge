# Benchmark TraceForge

Python 3.13.17 · Linux x86_64 · Intel(R) Xeon(R) Processor @ 2.10GHz (4 núcleos) · 3 repetições por combinação (mediana)

## Conversão por imagem

| Imagem | Qualidade | Tipo | Resolução | Entrada KB | SVG KB | SVG gzip KB | Caminhos | Cand. | SSIM | ΔE | Tempo s (mín–máx) | Fria s | CPU s | Pico RAM MB (+Δ) |
|---|---|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| assinatura.jpg | fast | lineart | 500x200 | 4.67 | 5.3 | 2.38 | 1 | 1 | 0.983 | 0.88 | 0.114 (0.109–0.154) | 0.28 | 0.12 | 161.1 (+57.4) |
| assinatura.jpg | balanced | lineart | 500x200 | 4.67 | 5.3 | 2.38 | 1 | 3 | 0.983 | 0.88 | 0.327 (0.303–0.332) | 0.547 | 0.345 | 162.6 (+58.7) |
| assinatura.jpg | best | lineart | 500x200 | 4.67 | 5.3 | 2.38 | 1 | 6 | 0.983 | 0.88 | 0.668 (0.619–0.673) | 0.713 | 0.695 | 162.5 (+58.6) |
| foto_cafe.jpg | fast | photo | 600x400 | 55.48 | 1058.49 | 382.31 | 2149 | 1 | 0.7651 | 4.33 | 1.3 (1.278–1.318) | 1.383 | 1.29 | 181.1 (+77.4) |
| foto_cafe.jpg | balanced | photo | 600x400 | 55.48 | 1621.59 | 579.97 | 4422 | 3 | 0.7984 | 3.75 | 3.952 (3.926–3.984) | 4.123 | 3.931 | 184.5 (+80.8) |
| foto_cafe.jpg | best | photo | 600x400 | 55.48 | 1621.59 | 579.97 | 4422 | 6 | 0.7984 | 3.75 | 7.289 (7.115–7.426) | 7.107 | 7.196 | 186.3 (+82.4) |
| foto_gato.jpg | fast | photo | 451x300 | 27.18 | 735.41 | 258.31 | 1547 | 1 | 0.8176 | 3.23 | 0.824 (0.762–0.84) | 0.851 | 0.794 | 158.0 (+54.1) |
| foto_gato.jpg | balanced | photo | 451x300 | 27.18 | 1086.26 | 380.45 | 2868 | 3 | 0.8548 | 2.71 | 2.236 (2.198–2.298) | 2.384 | 2.223 | 162.5 (+58.6) |
| foto_gato.jpg | best | photo | 451x300 | 27.18 | 1086.26 | 380.45 | 2868 | 6 | 0.8548 | 2.71 | 3.986 (3.923–4.265) | 4.162 | 3.916 | 161.6 (+57.8) |
| logo_marca.jpg | fast | logo | 420x240 | 8.27 | 4.28 | 1.76 | 5 | 1 | 0.9213 | 2.21 | 0.674 (0.668–0.717) | 1.141 | 0.796 | 213.0 (+109.1) |
| logo_marca.jpg | balanced | logo | 420x240 | 8.27 | 4.28 | 1.76 | 5 | 3 | 0.9213 | 2.21 | 2.536 (2.375–2.867) | 2.853 | 2.942 | 216.4 (+112.7) |
| logo_marca.jpg | best | logo | 420x240 | 8.27 | 4.19 | 1.71 | 5 | 6 | 0.9213 | 2.22 | 4.971 (4.959–4.988) | 5.66 | 5.772 | 262.4 (+158.8) |
| logo_skimage.png | fast | logo | 500x500 | 187.55 | 67.94 | 23.87 | 143 | 1 | 0.9145 | 2.69 | 3.187 (3.102–3.296) | 3.345 | 3.314 | 251.4 (+147.7) |
| logo_skimage.png | balanced | logo | 500x500 | 187.55 | 46.14 | 17.6 | 78 | 3 | 0.911 | 2.85 | 12.764 (12.575–12.773) | 12.958 | 13.064 | 283.2 (+179.4) |
| logo_skimage.png | best | logo | 500x500 | 187.55 | 44.68 | 17.37 | 69 | 6 | 0.9107 | 2.87 | 24.604 (24.512–26.397) | 24.466 | 25.481 | 302.9 (+199.3) |
| personagem.png | fast | logo | 300x300 | 4.56 | 15.77 | 4.79 | 10 | 1 | 0.9814 | 1.93 | 1.34 (1.288–1.474) | 1.541 | 1.47 | 235.9 (+132.0) |
| personagem.png | balanced | logo | 300x300 | 4.56 | 15.77 | 4.79 | 10 | 3 | 0.9814 | 1.93 | 4.225 (4.129–4.263) | 4.467 | 4.6 | 247.3 (+143.6) |
| personagem.png | best | logo | 300x300 | 4.56 | 15.77 | 4.79 | 10 | 6 | 0.9814 | 1.93 | 8.961 (8.942–9.29) | 9.116 | 9.732 | 249.1 (+145.1) |
| pixel_sprite.png | fast | pixel | 128x128 | 0.95 | 2.7 | 0.71 | 5 | 1 | 1.0 | 0.0 | 0.014 (0.012–0.015) | 0.118 | 0.014 | 124.6 (+20.7) |
| pixel_sprite.png | balanced | pixel | 128x128 | 0.95 | 2.7 | 0.71 | 5 | 1 | 1.0 | 0.0 | 0.012 (0.012–0.013) | 0.109 | 0.012 | 124.7 (+20.7) |
| pixel_sprite.png | best | pixel | 128x128 | 0.95 | 2.7 | 0.71 | 5 | 1 | 1.0 | 0.0 | 0.012 (0.012–0.013) | 0.107 | 0.012 | 124.7 (+20.7) |
| silhueta_cavalo.png | fast | lineart | 400x328 | 2.52 | 21.34 | 8.17 | 1 | 1 | 0.9788 | 0.46 | 0.16 (0.159–0.165) | 0.305 | 0.167 | 170.7 (+66.8) |
| silhueta_cavalo.png | balanced | lineart | 400x328 | 2.52 | 21.34 | 8.17 | 1 | 3 | 0.9788 | 0.46 | 0.465 (0.442–0.503) | 0.6 | 0.484 | 170.9 (+66.9) |
| silhueta_cavalo.png | best | lineart | 400x328 | 2.52 | 21.34 | 8.17 | 1 | 6 | 0.9788 | 0.46 | 0.911 (0.902–0.916) | 0.982 | 0.949 | 171.0 (+67.2) |

## Tempo por etapa (s, 1ª execução em regime)

| Imagem | Qualidade | ingestao | analise | preprocess | tracado | postprocess | avaliacao |
|---|---|--:|--:|--:|--:|--:|--:|
| assinatura.jpg | fast | 0.001 | 0.008 | 0.081 | 0.018 | 0.002 | 0.043 |
| assinatura.jpg | balanced | 0.001 | 0.009 | 0.136 | 0.058 | 0.003 | 0.114 |
| assinatura.jpg | best | 0.001 | 0.008 | 0.279 | 0.118 | 0.008 | 0.243 |
| foto_cafe.jpg | fast | 0.004 | 0.016 | 0.006 | 0.819 | 0.2 | 0.231 |
| foto_cafe.jpg | balanced | 0.004 | 0.017 | 0.021 | 2.58 | 0.626 | 0.735 |
| foto_cafe.jpg | best | 0.004 | 0.016 | 0.045 | 4.897 | 1.094 | 1.365 |
| foto_gato.jpg | fast | 0.002 | 0.012 | 0.003 | 0.469 | 0.182 | 0.154 |
| foto_gato.jpg | balanced | 0.002 | 0.012 | 0.011 | 1.39 | 0.44 | 0.44 |
| foto_gato.jpg | best | 0.002 | 0.013 | 0.023 | 2.434 | 0.719 | 0.792 |
| logo_marca.jpg | fast | 0.002 | 0.009 | 0.56 | 0.06 | 0.001 | 0.042 |
| logo_marca.jpg | balanced | 0.002 | 0.009 | 2.105 | 0.142 | 0.003 | 0.114 |
| logo_marca.jpg | best | 0.002 | 0.012 | 4.419 | 0.298 | 0.009 | 0.246 |
| logo_skimage.png | fast | 0.007 | 0.018 | 2.931 | 0.197 | 0.013 | 0.129 |
| logo_skimage.png | balanced | 0.01 | 0.018 | 11.616 | 0.674 | 0.052 | 0.394 |
| logo_skimage.png | best | 0.008 | 0.038 | 24.074 | 1.386 | 0.128 | 0.763 |
| personagem.png | fast | 0.001 | 0.011 | 1.288 | 0.134 | 0.003 | 0.036 |
| personagem.png | balanced | 0.002 | 0.013 | 3.733 | 0.395 | 0.008 | 0.111 |
| personagem.png | best | 0.002 | 0.01 | 8.201 | 0.841 | 0.017 | 0.218 |
| pixel_sprite.png | fast | 0.001 | 0.003 | 0.0 | 0.001 | 0.0 | 0.01 |
| pixel_sprite.png | balanced | 0.001 | 0.003 | 0.0 | 0.001 | 0.0 | 0.009 |
| pixel_sprite.png | best | 0.001 | 0.003 | 0.0 | 0.001 | 0.0 | 0.008 |
| silhueta_cavalo.png | fast | 0.001 | 0.011 | 0.062 | 0.029 | 0.004 | 0.054 |
| silhueta_cavalo.png | balanced | 0.001 | 0.01 | 0.164 | 0.087 | 0.012 | 0.153 |
| silhueta_cavalo.png | best | 0.001 | 0.01 | 0.339 | 0.179 | 0.023 | 0.328 |

## Totais por qualidade

| Qualidade | Tempo total s | SVG total KB | SSIM médio | ΔE médio |
|---|--:|--:|--:|--:|
| fast | 7.61 | 1911.2 | 0.9202 | 1.97 |
| balanced | 26.52 | 2803.4 | 0.9286 | 1.85 |
| best | 51.4 | 2801.8 | 0.9285 | 1.85 |

## Outros

- **cli_version_s_mediana**: 0.409
- **api_imagem**: logo_marca.jpg
- **healthz_ms_mediana**: 2.81
- **vetorizar_s_mediana**: 2.504
- **resposta_kb**: 4.31
- **cabecalho_relatorio_kb**: 0.15
- **pytest_s**: 3.66
- **pytest_resumo**: 33 passed, 1 warning in 3.18s
- **pytest_ok**: True
