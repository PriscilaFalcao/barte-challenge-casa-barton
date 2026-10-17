# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A one-day hackathon submission (Barte AI Services, "Case Tarvo", 16–17 Oct 2026; repo deadline **17/10 18:30**). Goal: close September/2026 for **Tarvo Pagamentos**, a niche sub-acquirer (~25 merchants, education/exchange travel) with two business lines:

- **CHECKOUT** — merchants receive card/Pix via acquirer **Orbe**; Tarvo earns MDR + anticipation fee.
- **REMESSA** — merchants pay schools abroad via FX partner **Ponte Câmbio**; Tarvo earns a share of the spread (email says 50% of realized spread).

Full brief: `01_instrucoes_participantes.docx` (Portuguese). Data pack description: `dados/00_LEIA-ME.md`. All data is synthetic.

Implementation status (blocks per `docs/PRD.md` section 11): B0 to B8 and B11 are done (orchestrator + Classificador/InterpreteTaxas/Investigador with cache in `cache/agentes/`, SQLite state in `data/` with queue, decisions, promoted rules, events and per-stage checkpoints; core, ingestion of all 6 files, merchant registry, rate resolver, checkout, remessa, divergences, notes, bank classification by rule, pendências with owner/blocking from config, I-R2, `saida/resumo.md`). The web UI (`src/tarvo/web.py`, `src/tarvo/web/`) and the root-level `README.md` / `HIPOTESES.md` are built. Business rules are generic for any month; only `src/config/defaults.yaml` holds case configuration (extra ECs, Atlas without contract, Casa do Estudante override until 2026-12-31, `recuperacao_pendentes` as a fallback, `alertas_lancamento`; the history-based recovery lives in `src/tarvo/estado/historico.py`). Finance answers up to 17/10 11h03 are reflected in `docs/PRD.md` 12.1.

**All code lives under `src/`**, tests (`src/tests/`) and helper scripts (`src/scripts/`) included. Python 3.11+ (a `.venv` with 3.13 is used locally).

```
.venv/bin/pip install -e .                       # once
.venv/bin/pytest                                  # whole suite (pytest runs src/tests)
.venv/bin/python -m tarvo fechar --mes 2026-09    # reads dados/, writes saida/ (+ execucao.log)
.venv/bin/python -m tarvo fila --mes 2026-09       # validation queue (state in data/ or $TARVO_ESTADO)
.venv/bin/python -m tarvo decidir --mes 2026-09 --id PEN-... --por Helena --motivo "..." --conta 4.2.06
.venv/bin/python src/scripts/inspecionar_b1.py    # manual inspection of ingestion + rate resolver
# API key: copy .env.example to .env (git-ignored) and fill ANTHROPIC_API_KEY. No key (or TARVO_SEM_IA=1) and no cache hit = no-AI mode: every exception stays in the human queue.
```

Nothing is dropped silently: structural skips (footer rows, ignored sheet, out-of-month lines) are counted in `saida/execucao.log`; rows that look like data but are not recognized raise `LayoutError`; an empty month fails instead of writing empty outputs.

## Hard constraints from the brief

- **Traceability is the core rule.** Every output number must point to source lines. `saida/rastro.csv` links each `id_saida` to origin rows, and `sum(valor)` per `id_saida` must equal the reported number. A total that doesn't reconcile with its source lines is scored as invented.
- **Consume files exactly as delivered** — no manual pre-cleaning. The solution must re-run in October on new files of the same format.
- **Don't let the AI (or code) invent business rules.** Unwritten rules live with Tarvo's finance team (Slack `#tarvo-financeiro`). When a rule is unknown: write the assumption in `HIPOTESES.md` and route uncertain cases to `pendencias.csv` with a reason and who decides, rather than guessing. False alarms in divergences count against the score.
- No fuzzy name matching accepted blindly — merchant names are inconsistent across sources; prefer CNPJ / Orbe EC code joins.
- Graded on numbers vs. a hidden answer key (25%) and on AI usage (20%): keep session transcripts in `PROMPTS/`, and log 2–4 key moments (incl. at least one where the AI was wrong) in `PROMPTS/MOMENTOS.md`.

Required root files: `README.md` (install/run from scratch, keys needed, known limitations), `HIPOTESES.md` (assumptions, questions asked, answers received), `PROMPTS/`, `saida/`, `src/`.

## Output contract (`saida/`, partly auto-graded)

CSV, `;` separator, `.` decimal, dates `YYYY-MM-DD`, CNPJ digits only (14). Extra columns allowed.

| File | Required columns |
|---|---|
| `comissoes_por_lojista.csv` | id_saida; cnpj; lojista; linha_negocio; comissao_brl |
| `divergencias_taxa.csv` | id_saida; cnpj; linha_negocio; ref_origem; taxa_contratada_pct; taxa_aplicada_pct; diferenca_brl |
| `notas_a_emitir.csv` | id_saida; tomador_cnpj; tomador; linha_negocio; valor_brl; discriminacao |
| `lancamentos_classificados.csv` | id_saida; banco; ref_origem; data; descricao; valor; conta_codigo; metodo; confianca |
| `pendencias.csv` | id_saida; tipo; ref_origem; valor_brl; motivo; quem_decide |
| `rastro.csv` | id_saida; arquivo_origem; ref_origem; valor |

Enums: `linha_negocio` ∈ CHECKOUT/REMESSA; `banco` ∈ AURORA/MERIDIANO; `metodo` ∈ REGRA/IA/HUMANO; `confianca` 0–1.

`ref_origem` conventions: Orbe → `id_transacao`; Ponte → `Nº Operação`; Aurora → physical file line number (`L9`, `L10`… 1-based, counting the bank header rows); Meridiano → `FITID`.

## Source data quirks (`dados/`)

Note: git still tracks these under `Data/`; the working tree renamed it to `dados/` (uncommitted).

- **01 Orbe CSV** — ASCII, CRLF, `;`, pt-BR dates and comma decimals. One row per transaction; `tipo_lancamento` includes sales, chargebacks/reversals and anticipations, linked via `id_referencia` / `data_venda_original`. Join to merchants via `cod_estabelecimento` (EC Orbe).
- **02 Taxas XLSX** — hand-maintained. Sheet `Taxas vigentes` has a title/notes block; real header is on row 5 with a two-level header (MDR columns by modality, then Antecipação, Spread remessa, Vigência, Obs). Messy: CNPJs in mixed formats (masked, digits, even numeric with lost leading zero), some missing EC codes, multiple rows per merchant with date-ranged validity (e.g. Bridge renegotiated from 15/09/2026), free-text `Obs`. Sheet `ANTIGO 2025 - nao usar` must be ignored.
- **03 Ponte EML** — quoted-printable body + base64 XLSX attachment (`PonteCambio_Relatorio_TARVO_092026.xlsx`). Sheet `Operações`: 4 title rows then header (`Nº Operação`, dates, CNPJ Cliente, Spread R$, Spread %, Spread Estimado R$ (D-1), Status Compliance, Observação…). Sheet `Resumo` has per-currency totals. Finance says it sometimes has duplicate operations and negative spreads.
- **04 Plano de contas** — ISO-8859-1, CRLF. Only `ACEITA_LANCTO=S` (ANALITICA) accounts are valid classification targets.
- **05a Aurora CSV** — UTF-8, `;`, 5-line bank header + blank line, column header at line 7, `SALDO ANTERIOR` row, footer rows (`SALDO FINAL`, disclaimer). Amounts pt-BR (`66.026,00`).
- **05b Meridiano OFX** — SGML OFX 1.02, CP1252/ISO-8859-1 (accented MEMOs break if read as UTF-8). Each `<STMTTRN>` has TRNTYPE, DTPOSTED, TRNAMT, FITID, CHECKNUM, MEMO; tags are not closed.
