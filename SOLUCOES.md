# TraceForge — pesquisa e soluções

> Documento histórico fornecido com o projeto original. Preços, versões, resultados e licenças de terceiros não foram integralmente revalidados nesta importação. Consulte as fontes antes de decidir uma integração. A versão executável mantém VTracer 0.6.x; detalhes de versões mais novas podem diferir.

Síntese de duas pesquisas paralelas (out/2026): uma mapeou as ferramentas que já existem, a outra levantou técnicas práticas de fóruns e a literatura acadêmica. Serviu de base para o fluxo implementado no repositório.

> **Sobre o Reddit:** o acesso ao reddit.com foi bloqueado para a ferramenta de leitura e a busca não devolveu threads de lá. As dicas práticas abaixo vêm de Hacker News, fóruns e lista do Inkscape, comunidade Glowforge, documentação (mkbitmap, Potrace, VTracer) e tutoriais. Se quiser incorporar threads específicas do Reddit, cole o texto delas que eu integro.

---

## 1. O que já existe

### Motores clássicos (traçado de bitmap)

| Ferramenta | Licença | Cor | Melhor para | Observação |
|---|---|---|---|---|
| **VTracer** (visioncortex) | MIT | sim | logos, ilustrações flat | Rust + bindings Python/Node/WASM; modo `stacked` evita frestas. **Motor escolhido.** |
| **Potrace** | GPL-2.0+ | não (só P&B) | logos P&B, scans | Referência de qualidade em curvas; última release 1.16 (2019). |
| AutoTrace | GPL (programa) / LGPL (lib) | parcial | traços, *centerline* | Modo centerline é útil para caligrafia. |
| ImageTracer.js | Unlicense | sim | arte simples, posterizado | Roda no navegador, presets prontos. |
| Inkscape Trace Bitmap | GPL | sim (scans) | uso manual | Não é automatizável de forma simples. |
| Primitive | MIT | sim | efeito artístico | Não traça: aproxima com formas geométricas. |
| SVGcode | GPL-2.0 | — | PWA no navegador | Potrace em WebAssembly + SVGO. |
| pixels2svg / vectorize-pixelart | GPL-3.0 | sim | pixel art | Polígonos exatos por cor. |
| edgesvg | Apache-2.0 | sim | — | Projeto novo com a mesma ideia do TraceForge (classifica, roteia, pontua com SSIM). Bom para acompanhar. |

### Serviços pagos

| Serviço | Como funciona | Preço (o que foi possível confirmar) |
|---|---|---|
| Vectorizer.AI | deep learning + algoritmos clássicos; API com SDKs | assinatura; termos proíbem usar a saída para treinar modelos |
| Vector Magic | mesmo dono do Vectorizer.AI | US$ 9,95/mês online ou US$ 295 desktop |
| Recraft Vectorize | API `POST /v1/images/vectorize`, até 16 MP | US$ 0,01 por requisição |
| Illustrator Image Trace | presets (Auto-Color, High/Low Color, P&B) | Creative Cloud |
| Kittl | modos cor e monocromático | 3 conversões grátis |

### Modelos de IA com código aberto

| Modelo | O que faz | Requisitos | Licença |
|---|---|---|---|
| **StarVector** (CVPR 2025) | imagem → código SVG (ícones, logos simples) | GPU; versões 1B e 8B | Apache-2.0 |
| **OmniSVG** (NeurIPS 2025) | imagem/texto → SVG, ícones e ilustrações | ~17–26 GB de VRAM | código Apache-2.0; dataset não comercial |
| **InternSVG** (ICLR 2026) | imagem/texto → SVG, edição de ícones | GPU | Apache-2.0 |
| DiffVG | rasterizador diferenciável — refina caminhos existentes | GPU/CUDA | Apache-2.0 |
| LIVE (CVPR 2022) | otimiza Bézier em camadas | lento (~horas em 1080p), toolchain antigo | Apache-2.0 |
| Im2Vec | VAE raster → vetor | arquivado em 2022 | Apache-2.0 |

Os modelos de IA ainda não servem para foto nem ilustração rica (o próprio StarVector avisa), e os comentaristas do HN alertam que LLMs não acertam coordenadas com precisão. Hoje o melhor custo-benefício é **traçado clássico com bom pré-processamento**; IA entra como reforço para ícones.

---

## 2. As dicas práticas que mais se repetem

**Antes de traçar (o que mais pesa)**
1. Entrada limpa vale mais que qualquer ajuste de parâmetro — ponto repetido no HN e nos fóruns.
2. Amplie imagens pequenas cerca de 2× com interpolação cúbica; 3× ou mais faz a interpolação inventar detalhe (doc do mkbitmap).
3. Pixel art: amplie com vizinho-mais-próximo e nunca use traçador genérico — as bordas ficam tortas (fórum do Inkscape; Kopf & Lischinski 2011).
4. Um borrão leve (raio ~1) antes do limiar remove ruído de compressão.
5. Remova o fundo antes de traçar.
6. Reduza a paleta para as cores reais; se as cores da marca são conhecidas, fixe-as.
7. Ajuste o limiar (threshold) olhando o resultado: cada ferramenta usa uma escala diferente.

**Traçando**
8. Trace uma cor por vez e empilhe (*stacked*) — é o que o VTracer faz internamente; *cutout* é mosaico, pior para editar.
9. Use filtro de manchas (*speckle*) proporcional ao menor detalhe que você quer manter.
10. Cantos arredondados demais → reduza o parâmetro de suavização de cantos, não aumente o borrão.

**Depois**
11. Simplifique em passadas pequenas; tolerância alta apaga detalhe sem avisar (Ramer–Douglas–Peucker).
12. Compacte com SVGO.
13. Compare lado a lado com zoom e corrija à mão os pontos críticos.
14. Gerando logo com IA para vetorizar depois? Peça traços e preenchimentos bem definidos e paleta mínima.

**Erros comuns:** traçar o JPEG pequeno direto; excesso de cores (milhares de caminhos); deixar manchinhas; usar preset de logo em foto; simplificação agressiva.

---

## 3. Soluções possíveis para o repositório

### A. Pipeline clássico inteligente — **implementado**
Classifica → pré-processa → VTracer → avalia vários candidatos → escolhe. Roda em CPU, sem GPU, sem custo por imagem, MIT. Cobre bem logo, ícone, personagem flat, traço, assinatura e pixel art.

Duas técnicas aplicadas que fizeram mais diferença nos testes:
- **Paleta edge-aware** — aprender as cores só nas regiões planas evita que o antialiasing vire cores "fantasmas".
- **Suavização de rótulos por votação** — num logo em JPEG reduziu o SVG de 131 KB para 4 KB com a mesma fidelidade.

### B. Versão 100% no navegador
VTracer compila para WebAssembly. Um site estático (Cloudflare Pages/Vercel) que vetoriza no próprio navegador do usuário: custo zero de servidor, privacidade total. A quantização e a suavização viram JS/WASM. Ótimo para uma ferramenta pública gratuita.

### C. Backend de IA opcional para ícones
Plugin `--motor starvector` que roda StarVector-1B (ou InternSVG) quando há GPU, e o avaliador escolhe entre a saída da IA e a clássica pelo mesmo score. Serve para ícones simples, onde a IA gera formas mais "humanas" (círculos de verdade em vez de curvas aproximadas).

### D. Refinamento diferenciável
Pegar o SVG do pipeline e otimizar posições/cores com DiffVG. No paper do DiffVG, partir de um traçado pronto e otimizar reduziu o erro em cerca de 2,5×. Custo: GPU e tempo.

### E. Conector de APIs pagas
Adaptador opcional para Recraft (US$ 0,01/imagem) ou Vectorizer.AI, com a chave do próprio usuário. Útil como comparação ou para quem quer o máximo de qualidade sem GPU. Atenção aos termos de uso.

---

## 4. Licenças — o que evitar

- **Potrace não está incluído.** A afirmação original de que qualquer uso torna o repositório inteiro GPL foi retirada por ser ampla demais. Qualquer integração futura deve avaliar a licença da versão específica, a forma de distribuição e a relação entre os componentes; executar um programa em processo separado não substitui essa análise.
- pixels2svg e vectorize-pixelart são GPL-3.0 — por isso o conversor de pixel art é próprio.
- Modelos de IA: a licença do código não garante a dos pesos nem a do dataset (o do OmniSVG é não comercial).
- Saídas de serviços pagos não devem virar dataset de treino sem ler os termos.

*Não é aconselhamento jurídico.*

---

## 5. Roadmap sugerido

1. **v0.1 (feito)** — CLI + Python + web local, 5 estratégias, auto-ajuste por métricas, testes.
2. **v0.2** — paleta fixa por parâmetro (`--paleta "#E65029,#1E3D8C"`), modo centerline para assinaturas, detecção de círculos/retângulos para trocar curvas por `<circle>`/`<rect>`.
3. **v0.3** — versão WASM no navegador (solução B) com deploy estático.
4. **v0.4** — backend de IA opcional (C) e refinamento DiffVG (D) atrás de flags.
5. **Benchmark público** — conjunto fixo de imagens (logos, ícones, personagens, fotos) com SSIM/ΔE/caminhos/bytes para comparar versões e motores.

---

## Fontes

- VTracer — https://github.com/visioncortex/vtracer
- Potrace e artigo de Selinger — https://potrace.sourceforge.net/ · https://potrace.sourceforge.net/potrace.pdf
- mkbitmap (pré-processamento) — https://www.mankier.com/1/mkbitmap
- AutoTrace — https://github.com/autotrace/autotrace
- ImageTracer.js — https://github.com/jankovicsandras/imagetracerjs
- SVGcode — https://github.com/tomayac/SVGcode
- Primitive — https://github.com/fogleman/primitive
- edgesvg — https://github.com/raphaelmansuy/edgesvg
- pixels2svg — https://pypi.org/project/pixels2svg/
- Depixelizing Pixel Art (Kopf & Lischinski 2011) — https://johanneskopf.de/publications/pixelart
- DiffVG — https://github.com/BachiLi/diffvg · https://people.csail.mit.edu/tzumao/diffvg/diffvg.pdf
- LIVE — https://github.com/Picsart-AI-Research/LIVE-Layerwise-Image-Vectorization
- StarVector — https://github.com/joanrod/star-vector · https://huggingface.co/starvector/starvector-1b-im2svg
- OmniSVG — https://github.com/OmniSVG/OmniSVG
- InternSVG — https://github.com/hmwang2002/InternSVG
- Im2Vec — https://github.com/preddy5/Im2Vec
- Revisão "Image Vectorization: a Review" — https://arxiv.org/abs/2306.06441
- SVG-Score (avaliação) — https://arxiv.org/abs/2609.03806
- Recraft Vectorize API — https://www.recraft.ai/docs/api-reference/tools/vectorize
- Vectorizer.AI — https://www.vectorizer.ai/
- Vector Magic — https://vectormagic.com/pricing
- Illustrator Image Trace — https://helpx.adobe.com/illustrator/using/image-trace-presets.html
- Kittl — https://www.kittl.com/tools/svg-converter
- Hacker News — https://news.ycombinator.com/item?id=46793060 · https://news.ycombinator.com/item?id=15025420
- Fórum do Inkscape — https://alpha.inkscape.org/vectors/www.inkscapeforum.com/viewtopicbbd7.html?t=1621 · https://alpha.inkscape.org/vectors/www.inkscapeforum.com/viewtopicd0e6.html
- Tutorial de traçado no Inkscape — https://www.norwegiancreations.com/?p=3269
- SVGO — https://github.com/svg/svgo
