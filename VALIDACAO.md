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
