# Tarvo

Motor de fechamento financeiro e interface local para conferir arquivos, executar o pipeline e consultar as saídas.

## Executar a interface

Instale o projeto e as dependências de desenvolvimento:

```powershell
python -m pip install -e ".[dev]"
```

Inicie a interface local:

```powershell
python -m tarvo web
```

Abra [http://127.0.0.1:8000](http://127.0.0.1:8000). O servidor escuta apenas no computador local. As execuções da interface ficam em `data/web/`.

Esta primeira etapa integra ao motor os arquivos da Orbe (`.csv`), taxas contratadas (`.xlsx`) e Ponte Câmbio (`.eml`). Plano de contas, extratos bancários, fila de decisões e configurações ainda não fazem parte do fluxo web.

## Executar pelo terminal

```powershell
python -m tarvo fechar --mes 2026-09 --dados dados --saida saida
```