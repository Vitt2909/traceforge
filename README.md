# TraceForge

**Transforme imagens em SVG com uma interface de arrastar e soltar, CLI ou Python.**

Logos, ilustrações, assinaturas e pixel art recebem tratamentos diferentes. O pipeline classifica a entrada, prepara a imagem, testa candidatos com VTracer e escolhe o resultado pelo equilíbrio entre fidelidade e complexidade. Roda em CPU; o fluxo padrão não usa APIs pagas, GPU ou serviços externos.

[![CI](https://github.com/Vitt2909/traceforge/actions/workflows/ci.yml/badge.svg)](https://github.com/Vitt2909/traceforge/actions/workflows/ci.yml)
[![Abrir no Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/Vitt2909/traceforge)

![Exemplos do pipeline original](exemplos/antes-depois.png)

## Começar

Use Python **3.10 ou superior** (3.12 recomendado). Clone o projeto e instale em um ambiente virtual:

```bash
git clone https://github.com/Vitt2909/traceforge.git
cd traceforge
python -m venv .venv
```

Ative o ambiente:

```bash
# macOS / Linux
source .venv/bin/activate
```

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Instale e inicie:

```bash
python -m pip install -e ".[web]"
traceforge-web
```

Abra **http://127.0.0.1:8000**, escolha uma imagem, clique em **Vetorizar**, compare as prévias e baixe o SVG. `python -m traco.web` é uma alternativa se o comando não estiver no PATH. No Windows, também é possível executar `.venv\Scripts\python.exe -m traco.web` sem ativar o ambiente.

**Pelo navegador, sem instalar localmente:** abra o botão Codespaces acima. Após preparar o ambiente, a porta 8000 abre a interface. O processamento acontece na máquina do Codespaces; o serviço tem cotas e possíveis custos definidos pelo GitHub. Isso ainda não é a futura versão WASM que processará tudo no próprio navegador.

## Linha de comando

```bash
traceforge logo.png
traceforge logo.jpg -o saida/logo.svg -t --relatorio
traceforge personagem.png -q best
traceforge "pasta/*.png" -o saida/
traceforge foto.jpg -p illustration -c 12
python -m traceforge logo.png
```

| Opção | Comportamento |
|---|---|
| `-o, --saida` | Arquivo `.svg` ou pasta; cria diretórios necessários |
| `-p, --preset` | `auto`, `logo`, `illustration`, `lineart`, `pixel`, `photo` |
| `-q, --qualidade` | `fast`: 1 candidato; `balanced`: 2; `best`: até 4, com parada por ganho marginal; pixel art usa 1 |
| `-c, --cores` | Máximo de 2–64 cores, apenas nos presets `logo` e `illustration` |
| `-t, --transparente` | Remove fundo uniforme conectado às bordas |
| `--relatorio` | Salva JSON com SSIM, ΔE76, nota estrutural, avisos, tempos, caminhos, paleta e candidatos |
| `--ia-fundo` | Remoção de fundo opcional; instale `python -m pip install -e ".[ai]"`; baixa pesos na primeira execução |
| `--otimizar` | Tenta executar SVGO via `npx`; exige Node.js e pode baixar o pacote. Se indisponível, mantém o SVG |

`traco`, `traco-web` e `from traco import vectorize` continuam funcionando por compatibilidade com o projeto original. Não é necessário instalar um pacote chamado `traco` do PyPI. Uma saída existente com o mesmo nome será substituída; imagens de entrada são protegidas contra sobrescrita.

## Python

```python
from pathlib import Path
from traceforge import vectorize

result = vectorize("logo.png", transparent=True, quality="balanced")
Path("logo.svg").write_text(result.svg, encoding="utf-8")
print(result.report())
```

## API local

```bash
curl -F "arquivo=@logo.png" -F "qualidade=balanced" \
  http://127.0.0.1:8000/api/vetorizar -o logo.svg
```

`POST /api/vetorizar` aceita `arquivo`, `preset`, `qualidade`, `cores` e `transparente`. Retorna SVG, nome de download em UTF-8 e métricas no cabeçalho `X-TraceForge-Report`. Documentação interativa em `/docs`; saúde em `/healthz`. Entrada inválida recebe 400/422, arquivo acima de 20 MB recebe 413 e outra conversão em andamento recebe 503.

## Docker

```bash
docker build -t traceforge .
docker run --rm -p 127.0.0.1:8000:8000 traceforge
```

O serviço foi feito para uso local e não tem autenticação. Para hospedagem pública, configure autenticação, limites de corpo de requisição, concorrência, tempo de processamento e recursos no proxy/ambiente de execução. O limite da aplicação é aplicado após o parser multipart do servidor. Uploads podem usar arquivos temporários, encerrados após a leitura. Imagens não são enviadas a APIs externas pelo pipeline padrão.

## Fluxo e limites

1. **Entrada:** PNG, JPG, WebP, GIF, BMP e TIFF. Corrige EXIF e usa o primeiro quadro de animações. Outros formatos dependem dos codecs do Pillow.
2. **Análise:** heurística para logo, ilustração, traço, foto ou pixel art; o preset manual permite corrigir a classificação.
3. **Pré-processamento:** redução de ruído, ampliação, paleta aprendida em regiões planas e suavização de rótulos por votação.
4. **Traçado:** VTracer 0.6.x em camadas; pixel art usa retângulos por cor e opacidade, preservando pixels.
5. **Saída:** SVG com `viewBox`, título escapado e dimensões originais.
6. **Avaliação:** mantém SSIM/ΔE76 para comparação e acrescenta recuperação de bordas, componentes pequenos e erro nas cores. A avaliação estrutural usa até 1536 px para não reduzir as letras da grade a metade do tamanho. Resultados com perda grave são marcados `rejected`; o CLI mostra `REJEITADO` e termina com código 2. Resultados duvidosos recebem `review`/`REVISAR`. A nota é heurística e não certifica legibilidade por OCR.

- Máximo de **20 MB e 20 megapixels**. O processamento reduz o maior lado a 4096 px, mas mantém as dimensões originais no SVG.
- Fotos geram muitos caminhos e arquivos grandes. Para um resultado mais leve e estilizado, use `-p illustration -c 12`.
- Fora do preset pixel, a transparência é simplificada para opaco/transparente; degradês viram faixas de cores sólidas.
- Texto vira contorno, não fonte editável. Assinaturas usam contornos, **não centerline**.
- O modo automático pode classificar pequenas artes como pixel art. Use `-p logo` quando desejar curvas.
- A v0.1 não inclui WASM, StarVector, DiffVG, paleta fixa, reconhecimento de primitivas ou conectores pagos.

## Correções de logos (0.1.1)

- Pequenas áreas coloridas impedem a classificação automática como preto e branco; o fundo não dilui a cor da marca.
- O traçado binário identifica tinta clara sobre fundo escuro. Uma saída binária reprovada no automático recebe uma tentativa colorida adicional.
- Hastes, acentos e outros traços finos são protegidos da suavização. A preservação de detalhes pode aumentar o SVG.
- A paleta é aprendida de uma amostra limitada e reutilizada entre candidatos. A atribuição de cores usa buscas em árvore em blocos, sem matrizes gigantes de distâncias.
- `best` começa com os mesmos candidatos de `balanced` e só continua enquanto há ganho de pelo menos 0,003 na pontuação; encerra ao atingir 0,97 de qualidade ou um platô. Candidatos extras reutilizam a paleta e a avaliação de referência.

[Comparação visual dos 10 logos e medições antes/depois](docs/logo-regressions/README.md).

```bash
python benchmarks/crop_logos.py tests/fixtures/logo-grid.png -o logos
python benchmarks/bench.py "logos/*.png" -r 2 --sem-extras --salvar-svg -o resultado-balanced
python benchmarks/bench.py "logos/*.png" -r 2 --sem-extras --salvar-svg -q best -o resultado-best
```

`bench.py --repo <checkout>` mede outra versão com o mesmo script. O tempo exclui imports e a renderização das comparações; o pico RSS inclui a memória do processo e das dependências. Os valores não devem ser comparados diretamente entre máquinas. O código 2 no CLI indica uma saída salva para inspeção, mas reprovada pela avaliação estrutural.

## Desenvolvimento e verificação

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build
```

A suíte cobre o pipeline, transparência, imagens pequenas, validação, arquivos em lote, API, nomes Unicode e disponibilidade do servidor durante conversões. O CI testa Python 3.10/3.12 em Linux, Windows e macOS e instala a wheel fora do repositório para conferir o empacotamento da interface.

Os exemplos e a comparação visual foram recebidos com a versão inicial. Seus números históricos não são um benchmark independente. Para reproduzir as métricas na sua máquina:

```bash
traceforge "exemplos/entrada/*" -o resultados/ --relatorio
```

Veja [SOLUCOES.md](SOLUCOES.md) para as notas de pesquisa e o roadmap.

## Licença

Código do TraceForge sob [MIT](LICENSE). Dependências e materiais de terceiros mantêm suas próprias licenças. O motor padrão é VTracer; Potrace não está incluído.
