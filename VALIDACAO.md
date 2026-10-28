# Validação da importação — TraceForge 0.1.0

- `python -m pytest -q`: **33 testes passaram** no Linux/Python 3.12.
- `python -m build --no-isolation`: wheel e sdist gerados com sucesso.
- Wheel instalada em um ambiente virtual separado, fora do checkout: importação, interface empacotada, `python -m traceforge --version` e conversão do logo JPEG passaram.
- Oito exemplos convertidos com qualidade `balanced`; métricas e versões em [exemplos/benchmark.json](exemplos/benchmark.json).
- API testada com TestClient: download SVG, nomes Unicode, entrada inválida, limites e resposta de saúde enquanto outra conversão está em andamento.
- JavaScript da interface validado com `node --check`. A inspeção visual em navegador automatizado não foi concluída: o ambiente não tinha Chromium e o download do navegador falhou. Não se atribui a esta rodada uma validação visual desktop/mobile.
- Docker e Codespaces configurados, mas não executados nesta rodada local.
- Windows/macOS e instalação da wheel estão definidos no [CI](https://github.com/Vitt2909/traceforge/actions/workflows/ci.yml); consulte a execução do commit para o resultado remoto.

Os resultados são testes deste conjunto, não uma garantia para qualquer imagem. A pesquisa em SOLUCOES.md foi preservada como documento histórico, com a afirmação excessivamente ampla sobre GPL retirada.


## Correção 0.1.1 — logos, detalhes e desempenho

- Benchmark do commit 1cb321a contra a versão corrigida, com 2 repetições por entrada/qualidade e subprocessos independentes.
- 10 recortes e grade completa, nas qualidades balanced e best: [tabelas, imagens e dados brutos](docs/logo-regressions/README.md).
- **55 testes passaram** no Linux/Python 3.12 (33 existentes + 22 novos). Os 33 testes existentes foram preservados. Novas regressões cobrem cor diluída pelo fundo, polaridade invertida, 12 regiões de textos pequenos, saída vazia, aviso/exit code no CLI, fallback colorido, reutilização de paleta e parada da busca.
- Inspeção visual das 10 pranchas original × antes × depois concluída. Os textos dos seis logos citados foram preservados. A fotografia do Horizonte segue com texto pequeno degradado e recebe aviso de revisão; não foi tratada como uma conversão perfeita.
- Queda de SSIM em Sabor & Arte e ForceFit: os fundos texturizados foram simplificados. O relatório mostra esse custo, os tamanhos maiores quando detalhes são retidos e as métricas por imagem.
- A falha preta do RapidCar foi reproduzida pelo caminho lineart forçado; os recortes usados nesta máquina ficaram no limite, mas foram classificados como logo pelo baseline automático. Essa diferença de reprodução está explicitada no relatório.
