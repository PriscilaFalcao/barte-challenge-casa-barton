# PRD de implementação: fechamento Tarvo, setembro/2026

Versão 2 (inclui interface web, seção 15) · 17/10/2026 · Base: `HIPOTESES.md`, `CHECKPOINTS.md`, `perguntas_slack.md`, `01_instrucoes_participantes.docx`

## 0. Como ler este documento

| Marca | Significado |
|---|---|
| ✅ | Regra confirmada pelo financeiro (ver `HIPOTESES.md`). Entra no código como regra fixa. |
| ⚠️ | Premissa nossa. Entra no código como parâmetro configurável, com default documentado. |
| 🟡 **V#** | **Validar com o financeiro.** Tem ID e está consolidado na seção 12. O código já funciona com o default, e a resposta só troca um parâmetro. |
| 🤖 | Ponto onde um agente de IA atua. Todo o resto é código determinístico. |
| 🧑 | Ponto onde um humano decide (human-in-the-loop). Sempre pela interface, nunca editando arquivo. |
| 🖥️ | Ponto de contato com o usuário de negócio na interface web (seção 15). |

---

## 1. Objetivo, escopo e critério de sucesso

**Objetivo.** Fechar setembro/2026 da Tarvo a partir dos 6 arquivos do data pack, como chegam, e gerar as 6 saídas em `saida/`. A mesma solução tem que rodar em outubro com arquivos novos no mesmo formato, sem mexer no código.

**Níveis de entrega** (ordem de construção, sem pular):

| Nível | Entrega | Saída que cobre |
|---|---|---|
| **Mínimo** | Comissão de checkout por lojista, com rastro | `comissoes_por_lojista`, `rastro` |
| **Alvo** | + comissão de remessa, divergências, notas, classificação dos extratos | + `divergencias_taxa`, `notas_a_emitir`, `lancamentos_classificados` |
| **Extra** | + pendências explicadas, rastro completo, reexecução em outubro | + `pendencias`, validadores, fila de decisões |

**Critério de sucesso** (testável, ver seção 10):

1. As 6 saídas existem, no formato fixo (`;`, `.` decimal, `AAAA-MM-DD`, CNPJ com 14 dígitos).
2. Para todo `id_saida`: `sum(rastro.valor) == número reportado`, em decimal exato.
3. Zero alarme falso conhecido: nenhuma divergência de R$ 0,01 por truncagem da Orbe.
4. Nenhuma regra inventada: o que o código não sabe vira linha em `pendencias.csv`, com motivo e `quem_decide`.
5. Rodar duas vezes com as mesmas entradas e decisões gera saídas idênticas (byte a byte, exceto o carimbo de execução no log).
6. 🖥️ Uma analista sem conhecimento técnico consegue, só pela interface: subir os arquivos do mês, acompanhar a execução, responder as validações, ver e baixar as 6 saídas e ajustar as regras de negócio. Nenhum passo exige abrir YAML, CSV de configuração ou terminal.
7. 🖥️ A interface não calcula nada: chama o mesmo motor da linha de comando. Os arquivos baixados são exatamente os de `saida/`.

**Fora de escopo** (já combinado em `CHECKPOINTS.md`): conciliação Orbe × banco parcela a parcela; faturar ou apontar divergência da Atlas; decidir devolução ou contestação; reconciliar jul/ago.

**Mudança de escopo (v2):** a interface web **entra** no escopo. O `CHECKPOINTS.md` ainda a lista como fora e deve ser atualizado no checkpoint 2. O brief diz que "mockup de tela não conta como solução" (a interface tem que chamar o motor real) e que não avalia capricho visual. Mesmo assim, a interface é a vitrine do pitch e precisa ter boa usabilidade (15.12). A corretude dos números vem sempre antes. O risco de tempo e a linha de corte estão nas seções 11 e 15.11.

---

## 2. Princípios de projeto

| # | Princípio | Consequência prática |
|---|---|---|
| P1 | **Determinístico primeiro, IA só na exceção.** | Tudo que tem regra escrita ou confirmada roda em Python puro, sem chamada de API. O agente só é chamado quando uma regra devolve "não sei". |
| P2 | **A IA nunca calcula dinheiro.** | Nenhum agente produz ou altera valor em R$, taxa ou data. Agentes só classificam, propõem vínculo ou redigem texto. Todo número sai de código com `Decimal`. |
| P3 | **Regra desconhecida vai para um humano.** | Agente que não tem regra produz uma *pergunta estruturada*, não um palpite. A pergunta aparece na fila de validação da interface (seções 8.4 e 15.6), e a resposta é aplicada reprocessando só as etapas afetadas. |
| P4 | **Rastro por construção.** | Cada cálculo emite suas linhas de rastro no mesmo passo que emite o valor. O rastro não é reconstruído depois. |
| P5 | **Sem casamento aproximado.** | Chaves: CNPJ normalizado, EC Orbe, `Nº Operação`, FITID, linha física. Nome só casa por igualdade exata após normalização, contra lista fechada. O que não casa vira pendência. |
| P6 | **Decimal exato, sem tolerância.** | `decimal.Decimal` em todo cálculo, `ROUND_HALF_UP` simétrico. Nada de `float`. Ver MOMENTOS 1: a tolerância de R$ 0,011 escondeu a truncagem da Orbe. |
| P7 | **Regra é configuração, não código, e quem a edita é o usuário de negócio pela interface.** | Tolerâncias, mapa de contas, overrides de taxa, aliases e responsáveis vivem como dados versionados no banco de estado, editados na tela Configurações (15.7). Os arquivos `config/*.yaml` existem só como defaults de fábrica e como modelo de dados. |
| P8 | **Reexecutável e idempotente.** | Mesma entrada + mesmas decisões = mesma saída. Respostas de agentes são cacheadas por hash da entrada. |
| P9 | **Falha visível.** | Arquivo com layout inesperado derruba a execução com mensagem clara. Nunca segue em silêncio com dado errado. **Nada some em silêncio:** só se descarta estrutura do arquivo (rodapé, aba ignorada, linha em branco, linha fora do mês), e tudo o que é descartado é contado em `execucao.log`. Linha que parece dado e não é reconhecida derruba a execução. |
| P10 | **Nenhum usuário de negócio toca em arquivo técnico.** | Sem YAML, sem CSV de configuração, sem terminal. Upload, validação, regras e download são telas. |
| P11 | **A interface mostra, não decide.** | A interface não calcula e não altera número. Ela envia arquivos e decisões à API e exibe o que o motor e os agentes fizeram, etapa por etapa. |
| P12 | **Toda mudança de regra é auditável.** | Cada alteração guarda autor, data, motivo, valor anterior, vigência e versão, e pode ser simulada antes de salvar e revertida depois. |

---

## 3. Arquitetura

```
┌─────────────────────────────────────────────────────────────────────┐
│ CAMADA 0 · INTERFACE WEB 🖥️  (seção 15)                             │
│  upload · pré-validação · workflow ao vivo · fila de validação ·    │
│  saídas (ver e baixar) · configurações · histórico                  │
└───────────────┬─────────────────────────────────────────────────────┘
                │ API: arquivos, decisões, regras     ▲ eventos de etapa
                ▼                                     │
 arquivos do mês (6, como chegam: upload ou pasta dados/)
        │
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│ CAMADA 1 · INGESTÃO (código)                                        │
│  orbe · taxas · ponte(.eml→.xlsx) · plano_contas · aurora · ofx     │
│  → tabelas canônicas, cada linha com (arquivo, ref_origem)          │
└───────────────┬─────────────────────────────────────────────────────┘
                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ CAMADA 2 · IDENTIDADE E CONTRATOS (código)                          │
│  registro de lojistas (CNPJ ↔ EC ↔ aliases) · resolvedor de taxa    │
│  vigente por (lojista, produto, data da venda)                      │
└───────────────┬─────────────────────────────────────────────────────┘
                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ CAMADA 3 · MOTORES (código, Decimal)                                │
│  checkout · remessa · divergências · notas · classificação bancária │
│  cada motor devolve: resultados + rastro + exceções (fila)          │
└───────────────┬─────────────────────────┬───────────────────────────┘
                │ resultados + rastro     │ exceções
                │                         ▼
                │          ┌──────────────────────────────────────────┐
                │          │ CAMADA 4 · ORQUESTRADOR + AGENTES  🤖🧑   │
                │          │  roteia cada exceção para o subagente    │
                │          │  certo; valida a saída do agente; se     │
                │          │  incerto, grava pergunta p/ humano       │
                │          └───────────────┬──────────────────────────┘
                │                          │ decisões (agente validado ou humano)
                ▼                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│ CAMADA 5 · CONSOLIDAÇÃO (código)                                    │
│  aplica decisões · gera pendências · valida invariantes             │
│  escreve as 6 CSVs + resumo.md + log de execução                    │
└─────────────────────────────────────────────────────────────────────┘
```

**Estado e eventos (suporte à interface).** Um banco SQLite (`data/tarvo.db`) guarda: fechamentos e seus arquivos, eventos de cada etapa (`run_eventos`), chamadas de agentes, fila de exceções, decisões, regras e parâmetros versionados, e o log de auditoria. O motor roda em segundo plano e **emite um evento por etapa** (início, contagens, alertas, fim). A interface só lê esses eventos. A execução é **por etapas com checkpoint**: cada etapa persiste seu resultado, então uma decisão nova reprocessa só as etapas que dependem dela (15.10).

**Decisão de arquitetura A1:** o orquestrador é **código** (máquina de estados em Python), não um LLM. Ele só roteia por `tipo_excecao` e não decide nada de negócio, então um LLM ali custaria dinheiro e latência e adicionaria não determinismo sem ganho. Os subagentes é que usam LLM. Se aparecer um tipo de exceção desconhecido, o orquestrador envia para a fila humana. 🟡 **V0** (decisão nossa, não do financeiro: confirmar se o time quer um orquestrador LLM por narrativa de pitch).

**Stack proposta:**

| Item | Escolha | Motivo |
|---|---|---|
| Linguagem | Python 3.11+ | Parsing de CSV, XLSX, EML e OFX na biblioteca padrão e `openpyxl`. |
| Dinheiro | `decimal.Decimal` | P6. |
| Planilhas | `openpyxl` (leitura) | Lê a aba por nome e o cabeçalho por texto. |
| E-mail | `email` (stdlib) | Extrai o anexo base64 do `.eml`. |
| OFX | parser próprio (regex sobre SGML) | As tags não fecham, e `ofxparse` costuma falhar nesse formato. |
| Agentes | SDK da Anthropic, saída estruturada (JSON validado por schema) | Controle total do contrato de entrada e saída. Haiku 5.5 para classificação, Sonnet 5.5 para casos de interpretação. |
| Testes | `pytest` | Seção 10. |
| Estado e configuração | SQLite | Regras versionadas, fila, decisões, eventos e auditoria num arquivo só, sem servidor. |
| API | FastAPI | Mesma base Python do motor. Eventos ao vivo por SSE. |
| Interface | Páginas renderizadas no servidor (Jinja + HTMX) com Tailwind e um kit de componentes pronto | Decisão A2: caminho mais rápido para um time de até 3 em um dia, e o kit dá um visual consistente sem desenhar do zero. React só se alguém do time já domina e não atrasa o B9. |
| Defaults de fábrica | YAML (`config/defaults.yaml`) | Só carga inicial do banco. O usuário nunca o edita. |

---

## 4. Estrutura do repositório

```
README.md                  instalar, rodar, chaves, limitações
HIPOTESES.md  PRD.md  CHECKPOINTS.md
PROMPTS/                   transcritos + MOMENTOS.md
dados/                     entrada (não editar)
saida/                     as 6 CSVs + resumo.md
config/
  defaults.yaml            carga inicial das regras: arredondamento, tolerâncias, flags (⚠️/🟡),
                           padrão de descrição → conta (7.7), ECs confirmados, aliases
data/                      tarvo.db, uploads/, execucoes/<id>/ (checkpoints por etapa); fora do git
src/tarvo/
  ingest/    orbe.py taxas.py ponte.py plano_contas.py aurora.py meridiano.py
  core/      money.py ids.py rastro.py excecoes.py competencia.py ledger.py
  identity/  registro.py
  contracts/ resolver.py
  engines/   checkout.py remessa.py divergencias.py notas.py bancos.py
  agents/    orquestrador.py base.py classificador.py interprete_taxas.py
             investigador.py   (+ prompts/*.md)
  output/    writers.py validators.py resumo.py
  estado/    db.py eventos.py config_versionada.py auditoria.py
  api/       app.py rotas_fechamentos.py rotas_config.py sse.py
  web/       templates/ static/        interface (seção 15)
  cli.py                       python -m tarvo fechar --mes 2026-09   (modo sem interface, mesmo motor)
src/tests/                     todo código, inclusive testes e scripts, fica em src/
  fixtures/  golden/           totais conferidos (seção 10)
src/scripts/                   utilitários de inspeção manual
cache/agentes/                 respostas de agentes por hash (versionadas)
```

**Convenção de leitura.** Nas seções 5 a 14, as menções a `config/regras.yaml`, `plano_contas_regras.yaml`, `lojistas_extra.yaml` e `decisoes.yaml` descrevem o **modelo de dados** de cada configuração. Em operação, esses dados vivem no banco e o usuário os edita na tela Configurações (15.7) e na fila de validação (15.6). O `defaults.yaml` só semeia o banco na primeira execução.

---

## 5. Modelo de dados canônico

Toda linha de entrada vira um registro com `arquivo_origem`, `ref_origem` e `valor` (assinado). Esses três campos são o que alimenta `rastro.csv`.

| Tabela | Chave de origem (`ref_origem`) | Campos principais |
|---|---|---|
| `orbe_tx` | `id_transacao` | tipo_lancamento, data_movimento, cod_estabelecimento, valor_bruto, taxa_aplicada_pct, qtd_parcelas, modalidade, id_referencia, data_venda_original |
| `taxas_contrato` | `Taxas!L<linha>` | cnpj14, ec_orbe, mdr por modalidade e faixa, antecipação, spread_remessa, vigencia_ini, vigencia_fim, obs |
| `ponte_op` | `Nº Operação` | data_contratacao, cnpj14, valor_me, ptax, spread_rs, spread_pct, status, observacao |
| `aurora_lan` | `L<linha física>` | data, descricao, valor |
| `meridiano_lan` | `FITID` | data, descricao (MEMO), valor, trntype |
| `plano_contas` | `codigo` | descricao, aceita_lancto, tipo |

**Registro de lojistas** (`identity/registro.py`). É a "chave que liga CNPJ ↔ EC ↔ nome", a resposta direta à H1.

| Campo | Origem |
|---|---|
| `cnpj14` (chave primária) | Planilha, normalizado: só dígitos, completado com zeros até 14. Cobre CNPJ com máscara, sem máscara e numérico sem o zero à esquerda. |
| `ec_orbe` (0..n) | Planilha, mais `config/lojistas_extra.yaml` (✅ C7: 1043300981, 1043396662, 1038867654). |
| `nome_canonico` | Planilha. |
| `aliases` | Grafias vistas na Orbe e nos bancos, **só as que casam exatamente após normalização** (caixa, acento, espaço, pontuação). |
| `status` | ATIVO / INATIVO (Obs "INATIVO") / SEM_CONTRATO (Atlas). |

Regras de junção, em ordem: (1) EC Orbe → lojista; (2) CNPJ normalizado → lojista; (3) alias exato → lojista; (4) nada casou → exceção `ENTIDADE_NAO_RESOLVIDA` (vai para a camada 4). Nunca existe um passo "nome parecido".

---

## 6. Esquema de `id_saida` e rastro

`id_saida` é determinístico, derivado da natureza do número. Não há contador, então a rodada de outubro gera ids estáveis e comparáveis.

| Saída | Padrão de `id_saida` | Exemplo |
|---|---|---|
| comissões | `COM-<LINHA>-<cnpj14>-<AAAAMM>` | `COM-CHK-66564512000199-202609` |
| divergências | `DIV-<LINHA>-<ref_origem>` | `DIV-CHK-TX88428053` |
| notas | `NF-CHK-<cnpj14>-<AAAAMM>` e `NF-REM-<AAAAMM>` | `NF-REM-202609` |
| lançamentos | `LAN-<BANCO>-<ref_origem>` | `LAN-AUR-L34` |
| pendências | `PEN-<tipo>-<ref_origem>` | `PEN-CONTESTACAO_PONTE-PC-0926-0162` |

**Linhas de rastro por saída** (`rastro.csv`, uma linha por origem × componente):

| Saída | Origem de cada linha | `valor` da linha de rastro | Invariante |
|---|---|---|---|
| Comissão CHECKOUT | cada `id_transacao` (venda, estorno, antecipação, reversão) | comissão da linha, já arredondada, com sinal | Σ = `comissao_brl` |
| Comissão REMESSA | cada `Nº Operação` aceita | 50% do `Spread R$`, arredondado | Σ = `comissao_brl` |
| Divergência | a transação ou operação da linha | `diferenca_brl` | Σ = `diferenca_brl` (1 linha) |
| Nota | as mesmas linhas das comissões que compõem a nota | idem comissão | Σ = `valor_brl` da nota |
| Lançamento | a linha do extrato | `valor` do lançamento | Σ = `valor` |
| Pendência | linha(s) que motivam a pendência | `valor_brl` | Σ = `valor_brl` |

Colunas extras no `rastro.csv`: `componente` (`MDR`, `ANTECIPACAO`, `SPREAD`), `taxa_usada_pct`, `regra_id` (ex.: `C1`, `R1`). Isso permite à analista auditar *qual regra* produziu cada centavo.

Quando uma nota inclui valor que tem **pendência associada** (excesso da Mundo Aberto, ✅ R4), a linha de rastro da pendência referencia o mesmo `ref_origem`, e o `id_saida` da pendência não entra na soma da nota.

---

## 7. Pipeline: estágios e regras

Cada estágio é um módulo com entrada e saída tipadas. Cada um devolve `(resultados, rastro, exceções)`.

### 7.1 Ingestão (camada 1)

| Fonte | Leitura | Armadilhas tratadas | Falha explícita se |
|---|---|---|---|
| Orbe CSV | UTF-8/ASCII, `;`, CRLF, datas pt-BR, vírgula decimal | `id_referencia` e `data_venda_original` só em estorno/reversão | colunas obrigatórias ausentes |
| Taxas XLSX | cabeçalho achado pelo texto "Lojista"/"CNPJ"/"EC Orbe", não pela linha 5; cabeçalho de dois níveis (MDR por modalidade, depois Antecipação, Spread, Vigência, Obs) | aba cujo nome contém "ANTIGO" ou "nao usar" ignorada; CNPJ em 3 formatos; taxa como texto (`'1,49%'`); vigência em texto livre | nenhuma coluna de taxa reconhecida |
| Ponte EML | extrai o anexo base64 e lê a aba `Operações`; cabeçalho achado pela célula "Nº Operação" | linha é operação se o ID começa com `PC-`; rodapé e aba `Resumo` **não** são fonte; dedup por `Nº Operação`. Linha sem `PC-` que tenha CNPJ, Valor ME ou Spread R$ **não** é rodapé: falha com a linha física | mais de um anexo XLSX, ou nenhum |
| Plano de contas | Latin-1, CRLF | só `ACEITA_LANCTO=S` é destino válido | — |
| Aurora CSV | UTF-8, `;`; cabeçalho de colunas no meio do arquivo; `ref_origem` = linha física (`L9`…); descarta `SALDO ANTERIOR`, `SALDO FINAL` e aviso; **verifica a cadeia de saldos** linha a linha | valores `66.026,00` | cadeia de saldos não fecha |
| Meridiano OFX | CP1252, SGML sem tags de fechamento; `<STMTTRN>` com TRNTYPE, DTPOSTED, TRNAMT, FITID, MEMO | acentos inconsistentes ("AÉREA"/"AEREA") | FITID duplicado ou ausente |

**Mês de referência.** Parâmetro `--mes 2026-09`. Competência da checkout = data do movimento (estorno abate no mês do estorno, ✅ C3). Competência da remessa = data de contratação (✅ R8).

**Linhas descartadas (ledger).** O código só descarta o que é estrutura do arquivo. Cada descarte é contado por fonte e motivo (`fora do mês`, `rodapé ou linha sem dado`), com amostra de referências, e aparece em `saida/execucao.log`. Linha totalmente em branco não conta. Planilha de taxas: linha sem nome de lojista mas com CNPJ, EC ou taxa falha (não é rodapé). **Gate de mês:** se nenhuma linha da Orbe nem da Ponte cai no mês pedido, a execução falha ("os arquivos são de outro mês?"), em vez de escrever saídas vazias. Se só uma das fontes estiver vazia, o log traz um aviso.

### 7.2 Resolvedor de taxa vigente (camada 2)

Função pura `taxa(lojista, produto, data_venda) → (Decimal, regra_id, linha_planilha)`.

- `produto` ∈ débito, crédito 1x, crédito 2–6x, crédito 7–12x, Pix, antecipação, spread remessa. ⚠️ 🟡 **V11** (a divisão por faixa de parcelas é leitura direta das colunas da planilha).
- Várias linhas por lojista com vigência: escolhe a linha cuja janela contém `data_venda`. Mais de uma janela cobrindo a data, ou nenhuma, gera exceção `CONTRATO_AMBIGUO` ou `CONTRATO_AUSENTE`.
- Estorno usa `data_venda_original` (✅ C3, C6). Se a venda original é de agosto, usa a planilha atual na data de agosto, e registra no rastro `regra_id = C3-HISTORICO` 🟡 **V14**.
- Sobreposições conhecidas: Bridge muda o crédito à vista para 2,19% a partir de 15/09 (✅ C6). Casa do Estudante: taxa 0 em MDR e antecipação de set a dez (✅ C8). A planilha ainda mostra 2,69%, então o override vem de `config/regras.yaml` com fonte e data. Atlas: `SEM_CONTRATO`, sem taxa (✅ C9).
- 🤖 Vigência em texto livre que a gramática (`até dd/mm/aaaa`, `a partir de dd/mm/aaaa`, data) não entende vai para o agente `InterpreteTaxas` (seção 8). A saída dele **não** vale sozinha: vira exceção para confirmação humana, porque é regra de contrato.

### 7.3 Motor de checkout

Para cada linha da Orbe do mês:

| Tipo | Comissão da linha | Regra |
|---|---|---|
| VENDA | `round(bruto × taxa_contratada(data_venda))` | ✅ C1, C2 |
| ESTORNO | `-round(bruto × taxa_contratada(data_venda_original))` | ✅ C3 |
| ANTECIPACAO | `round(bruto × taxa_antecipacao_contratada)`, componente `ANTECIPACAO` | ✅ C4 |
| REVERSAO_ANTECIPACAO | anula só a taxa da antecipação revertida, via `id_referencia` | ✅ C4 |

- `round` = meio centavo para cima, simétrico no negativo (−0,005 → −0,01). ✅ C2
- A base **nunca** é o `valor_taxa` da Orbe (✅ C1).
- Agregação: Σ por `(cnpj14, CHECKOUT)`. O arredondamento acontece por linha, antes da soma.
- Linha cujo EC não resolve para lojista gera exceção `ENTIDADE_NAO_RESOLVIDA`. Para Atlas (EC 1076801732, 57 linhas) o motor devolve `SEM_CONTRATO` e **não** calcula comissão (✅ C9).

### 7.4 Motor de remessa

Para cada operação da Ponte, depois do dedup:

| Caso | Tratamento | Regra |
|---|---|---|
| Operação normal | comissão = `round(0,50 × Spread R$)` | ✅ R1 |
| `Nº Operação` repetido | conta uma vez; a repetição vira pendência para a Ponte corrigir o relatório (hoje: `PC-0926-0162`, R$ 410,94 de comissão inflada) | ✅ R6 |
| `Spread R$` < 0 | fora da comissão e da nota; pendência de contestação | ✅ R5 |
| Status "APROVADO C/ RESSALVA" | ignorado | ✅ R7 |
| Mundo Aberto (1,5% contra 1,2%) | comissão pelo realizado, incluindo o excesso; divergência pelo valor cheio; pendência de contestação | ✅ R3, R4 |
| Data de contratação em 30/09, liquidação em 01/10 | entra em setembro | ✅ R8 |

Spread contratado: célula em branco ou "padrão" = 1,5% sobre a PTAX (✅ R2).

### 7.5 Motor de divergências

**Checkout (✅ D1, D2).** Compara **taxa**, não valor: `taxa_aplicada_pct` (Orbe) contra `taxa_contratada_pct` (resolvedor), ambas com 2 casas, igualdade exata. Se diferem: `diferenca_brl = round(bruto × (aplicada − contratada))`. Isso elimina por construção os ~1.000 alarmes falsos de R$ 0,01 da truncagem. 🟡 **V10** (a regra é do financeiro, a forma de comparar é nossa).

- Estorno com taxa diferente da contratada na data da venda original entra como divergência, com sinal negativo (a Orbe já devolveu parte do excesso). ⚠️ D4, 🟡 **V15**.
- Casa do Estudante: tudo que foi cobrado é divergência, pois o contratado é 0 (✅ C8).
- Atlas: nenhuma divergência (⚠️ D5, 🟡 **V5**).

**Remessa (⚠️ R10, R11).** `diferenca_brl = round(ME × PTAX × (spread_pct_aplicado − spread_pct_contratado))`, só acima de 0,01 p.p. de diferença (o ruído da Ponte é ±0,0016 p.p. e o desvio real da Mundo Aberto é ≈0,30 p.p.). 🟡 **V8** (R10: a fórmula alternativa via `Spread R$` dá R$ 0,03 a mais), 🟡 **V9** (R11: tolerância aceita pela Helena desde que escrita).

- Spread negativo entra também em `divergencias_taxa.csv` pela diferença contrato × realizado (Σ R$ 3.565,98), além da pendência de contestação. ⚠️ R12, 🟡 **V4**. É um `flag` em `config/regras.yaml` (`spread_negativo_em_divergencias: true`), então a resposta do financeiro vira uma mudança de uma linha.

### 7.6 Motor de notas

| Nota | Regra | Status |
|---|---|---|
| CHECKOUT | 1 por lojista por mês, tomador = lojista, valor = comissão total (MDR + antecipação − estornos) | ✅ N1, C4 |
| CHECKOUT com comissão ≤ 0 | **não emite**; pendência para a Helena; não passa para o mês seguinte | ✅ N2 |
| REMESSA | 1 nota, tomador Ponte Câmbio (CNPJ 75374179000146), valor = Σ das comissões de remessa aceitas | ✅ N3 |
| Atlas | sem nota | ✅ C9 |
| `discriminacao` | template fixo: `"Comissão sobre serviços de checkout, competência 09/2026"` e equivalente para remessa. **Sem IA.** | ✅ N4 (texto livre) |

Casa do Estudante: comissão de checkout negativa (estorno TX88445133 de venda de 21/08 a 1,49% = −R$ 5,50), então sem nota e com pendência. 🟡 **V3**. A remessa da Casa entra normal na nota da Ponte.

### 7.7 Motor de classificação bancária

Regra geral (✅ Fox AI 21h08): `conta_codigo` é a **contrapartida** do movimento. O que já estava provisionado baixa a conta onde estava. Despesas diretas vão para a conta de despesa.

Ordem de decisão por lançamento:

1. **REGRA** (confiança 1,0): a descrição casa com um padrão inequívoco em `config/plano_contas_regras.yaml` (tabela da seção 2.5 do `HIPOTESES.md`). O validador confere que a conta existe e tem `ACEITA_LANCTO=S`.
2. **REGRA com pendência**: a regra existe mas a contrapartida depende de decisão (PIX R$ 18.240 sem operação, devolução de R$ 12.400, PIX sem identificação L50). Classifica com a conta provisória e abre pendência. `metodo=HUMANO` até haver decisão.
3. 🤖 **IA** (confiança < 1,0): nenhum padrão casou. Vai para o agente `Classificador` (seção 8.2). Confiança ≥ 0,8 e conta válida: aceita com `metodo=IA`. Menor que isso: `metodo=HUMANO` e pendência.

Conciliação mínima determinística no Meridiano (sem IA): TED da Ponte do dia = Σ(`Valor R$` + IOF) das operações contratadas naquele dia. Quando bate, o lançamento ganha `regra_id = MER-TED-PONTE` e prova que a operação existe. PIX recebido de lojista cujo valor **não** bate com nenhuma soma por lojista gera a pendência do R$ 18.240.

🟡 **V7**: contas ⚠️ do `HIPOTESES.md` ainda sem confirmação: TED Orbe (1.1.03.001), PIX a lojistas (2.1.01.001), PIX/TED de remessas (2.1.02.001), CDB, rendimento, IOF s/ operação de crédito, tarifa de câmbio, seguro.

### 7.8 Pendências (camada 5)

`pendencias.csv` é alimentada por todos os motores via `excecoes.py`. Cada exceção tem tipo, `ref_origem`, `valor_brl`, `motivo` (template por tipo) e `quem_decide` (tabela abaixo, vinda de `config/regras.yaml`).

| Tipo | Origem | `quem_decide` | Status |
|---|---|---|---|
| `DIVERGENCIA_ORBE` | motor de divergências | Helena | ✅ D3 |
| `CONTESTACAO_PONTE` | duplicata, spread negativo, Mundo Aberto | Helena | ✅ R9 |
| `COMISSAO_NAO_POSITIVA` | N2 (Casa) | Helena | ✅ N2 |
| `SEM_CONTRATO` | Atlas | Diego (comercial) | ⚠️ 🟡 **V6** |
| `CASA_DEVOLUCAO` | cobrado indevido | Helena, com Diego | ⚠️ 🟡 **V6** |
| `LANCAMENTO_SEM_ORIGEM` | PIX R$ 18.240, L50 | Helena | ⚠️ 🟡 **V1**, **V6** |
| `REPASSE_ATIPICO` | R$ 112.220,15 à Atlas em 10/09 (L34) | Helena | ⚠️ 🟡 **V2** |
| `DEVOLUCAO_PIX` | L65, R$ 12.400 | Helena | ⚠️ 🟡 **V12** |
| `ENTIDADE_NAO_RESOLVIDA` | EC ou nome sem cadastro | Helena | ⚠️ |
| `CONTRATO_AMBIGUO` | vigência sobreposta ou ausente | Helena (planilha: Bia) | ⚠️ |
| `CLASSIFICACAO_BAIXA_CONFIANCA` | agente < 0,8 | Helena | ⚠️ |
| `CONFERIR_OUTUBRO` | transferência R$ 300 mil (L92) cai em 01/10 | Helena | ✅ I11 |

### 7.9 Consolidação e validação

Antes de escrever qualquer arquivo, o validador roda e **aborta com erro** (não escreve saída parcial) se algum invariante falhar:

| Invariante | Verificação |
|---|---|
| I-R1 | `sum(rastro.valor)` por `id_saida` = número reportado em cada uma das 5 outras saídas, em `Decimal` exato |
| I-R2 | todo `ref_origem` do rastro existe na tabela canônica da sua fonte |
| I-R3 | toda linha da Orbe do mês e toda operação da Ponte aceita aparece em pelo menos uma linha de rastro (de comissão, divergência ou pendência). Verificado em toda execução, por arquivo de origem |
| I-C1 | nenhuma conta de `lancamentos_classificados` é analítica = N |
| I-C2 | CNPJ com 14 dígitos; `linha_negocio`, `banco`, `metodo` dentro dos enums; `confianca` ∈ [0,1] |
| I-N1 | nenhuma nota com `valor_brl` ≤ 0 |
| I-B1 | cadeia de saldos da Aurora fecha |
| I-D1 | nenhuma divergência de checkout com `taxa_aplicada == taxa_contratada` |

Também escreve `saida/resumo.md` (legível para o financeiro: totais por linha, dinheiro em jogo, lista de pendências) e `saida/execucao.log` (arquivos lidos, linhas por fonte e no mês, linhas descartadas por motivo, avisos, validações e contagem de cada saída; sem carimbo de data, para ser idêntico entre execuções).

---

## 8. Camada de agentes 🤖🧑

### 8.1 Princípio de acionamento

O agente só é chamado quando um motor devolve uma **exceção do tipo "não sei"**. Matriz do que é código e do que é agente:

| Tarefa | Quem faz | Por quê |
|---|---|---|
| Ler os 6 arquivos | Código | Formato determinístico. |
| Normalizar CNPJ, taxas, datas | Código | Regras finitas. |
| Casar EC/CNPJ/alias | Código | P5: chave exata. |
| Comissão, estorno, antecipação, spread | Código | Regra confirmada. |
| Divergência de taxa e de spread | Código | Regra confirmada. |
| Notas, discriminação | Código | Template. |
| Dedup, spread negativo, duplicata | Código | Regra confirmada. |
| Classificar lançamento com padrão conhecido | Código (REGRA) | ~90% dos lançamentos. |
| Classificar lançamento sem padrão | 🤖 `Classificador` | Descrição livre, pouco volume. |
| Vigência/Obs em texto livre fora da gramática | 🤖 `InterpreteTaxas` (+ 🧑) | Interpretação de linguagem natural, mas regra de contrato exige confirmação. |
| Anomalia sem regra (PIX sem operação, repasse atípico) | 🤖 `Investigador` (+ 🧑) | Levanta evidências cruzando fontes e redige o motivo. Não decide. |
| Decidir devolução, contestação, faturar Atlas | 🧑 | Decisão do financeiro/comercial. |
| Qualquer regra de negócio nova | 🧑 | Pergunta estruturada (8.4). |

### 8.2 Subagentes

Contrato comum: entrada JSON mínima (só o que o agente precisa, sem o arquivo inteiro), saída JSON validada por schema, `temperature=0`, cache por hash da entrada em `cache/agentes/`.

**`Classificador`** (classificação bancária sem regra)
- Entrada: `{banco, data, descricao, valor, candidatos: [{codigo, descricao}]}`. Os candidatos são só contas analíticas (`ACEITA_LANCTO=S`) pré-filtradas por sinal do valor e por palavra-chave, no máximo 8.
- Saída: `{conta_codigo, confianca, justificativa}`.
- Guardrail em código: `conta_codigo` tem que estar em `candidatos`. Fora da lista, descarta e abre pendência.
- Modelo: Haiku 5.5.

**`InterpreteTaxas`** (texto livre da planilha)
- Entrada: `{lojista, obs, vigencia_texto, linhas_vizinhas}`.
- Saída: `{vigencia_ini, vigencia_fim, taxas_afetadas, confianca, trecho_que_justifica}` ou `{ambiguo: true, pergunta}`.
- **Nunca aplica sozinho.** O resultado entra como decisão proposta na fila (8.4), e só passa a valer depois da confirmação humana. Motivo: é regra de contrato, e erro aqui contamina comissão e divergência.
- Modelo: Sonnet 5.5.

**`Investigador`** (anomalias sem regra)
- Entrada: a exceção mais um pacote de evidências montado **por código** (movimentos do lojista nas três fontes na janela de datas, saldos).
- Saída: `{hipoteses: [{descricao, evidencia_refs[], plausibilidade}], pergunta_sugerida, quem_decide_sugerido}`.
- Guardrail: toda `evidencia_ref` tem que existir na tabela canônica. Não produz valor em R$. A saída preenche `motivo` e `pergunta_sugerida` da pendência.
- Casos de hoje: R$ 18.240 Ponte Aérea, R$ 112.220,15 Atlas, devolução R$ 12.400.
- Modelo: Sonnet 5.5.

### 8.3 Orquestrador

```
for exc in fila_excecoes:
    if decisao := decisoes.yaml.buscar(exc.chave):        # humano já respondeu
        aplicar(decisao); continue
    agente = ROTAS.get(exc.tipo)                           # tabela fixa
    if agente is None:
        fila_humana.add(exc); continue
    saida = agente.executar(exc)                           # cache por hash
    if not guardrail_ok(saida) or saida.confianca < LIMIAR[exc.tipo]:
        fila_humana.add(exc, proposta=saida); continue     # P3
    aplicar(saida, metodo="IA")
```

- `ROTAS` e `LIMIAR` ficam em `config/regras.yaml`.
- Limite de chamadas por execução (`max_chamadas_llm`, default 60). Estourou, o restante vai para a fila humana. Isso limita custo e impede loop.
- Sem chave de API, o orquestrador roda em **modo sem IA**: toda exceção vai para a fila humana. As saídas continuam completas e corretas, só com mais pendências. O README documenta isso.

### 8.4 Human-in-the-loop

1. A exceção que ninguém resolveu vira um **cartão na fila de validação** da interface (15.6), com: `chave`, tipo, `ref_origem`, valor, pergunta, proposta do agente (se houver), evidências com link para as linhas de origem e `quem_decide`. A mesma fila pode ser exportada em CSV, mas a interface é o canal de resposta.
2. A pessoa responde no cartão: aceita a proposta, escolhe outra opção ou encaminha. Ela marca o escopo: **"só neste caso"** ou **"sempre que acontecer"**. O sistema grava a decisão (`decisao`, `decidido_por`, `data`, `escopo`) e mostra antes o impacto ("isto afeta 3 lançamentos deste mês").
3. O sistema reprocessa só as etapas afetadas. O lançamento ou a pendência passa a sair com `metodo=HUMANO` e `confianca=1`. Decisão de escopo "sempre que acontecer" **vira regra** no mesmo ato, na tela, sem comando: entra em Configurações como nova versão, com autor e data, e passa a valer para esse padrão nos próximos fechamentos. **O agente nunca grava regra.** Só uma pessoa, pela interface, promove.
4. Efeito composto: a cada fechamento, menos exceções, pois o que o humano ensinou vira regra determinística. É a resposta direta a "se eu sair de férias, o mês não fecha".

Toda pergunta nova segue a lista de perguntas já feitas em `perguntas_slack.md` para não repetir pergunta que outro time fez e foi respondida (a banca publica as respostas no canal).

### 8.5 Ciclo de vida de uma exceção

```
DETECTADA ─► já há decisão?  ──sim──► APLICADA (metodo=HUMANO)
    │ não
    ▼
 há agente para o tipo? ──não──► AGUARDANDO_HUMANO
    │ sim
    ▼
 AGENTE_PROPÔS ─► guardrail e confiança ok? ──sim──► APLICADA (metodo=IA)
                        │ não
                        ▼
                  AGUARDANDO_HUMANO ──► DECIDIDA(caso | regra) ──► APLICADA
                        │                                              │
                        └─► resposta não cabe em nenhuma regra         └─ se "regra": nova versão
                            configurável ► REQUER_IMPLEMENTACAO           em Configurações
```

- **Tratamento seguro enquanto aguarda.** O item sai nas saídas com o default documentado (por exemplo, conta provisória e pendência) e marcado como **provisório**. Nunca fica em branco e nunca é adivinhado.
- **Bloqueante ou não.** Cada tipo de exceção é classificado em Configurações como *bloqueante para fechar* (muda comissão ou nota: contrato ambíguo, lojista não identificado, vigência interpretada por agente) ou *não bloqueante* (classificação de lançamento, contestação). O fechamento do mês só é liberado sem itens bloqueantes provisórios (15.5, gate G4).
- **Regras promovíveis pela interface.** Só existem estes tipos, cada um com formulário próprio. Tudo fora disso é `REQUER_IMPLEMENTACAO`.

| Tipo de regra | Formulário na tela | Exemplo |
|---|---|---|
| Padrão de descrição → conta | texto do padrão + seletor de conta analítica | "PIX RECEB PONTE AEREA" → 2.1.02.001 |
| Override de taxa com vigência | lojista, produto, taxa, início e fim | Casa do Estudante, MDR 0%, set a dez/2026 |
| Lojista, EC e alias | CNPJ, EC, grafia exata | EC 1043396662 → Horizonte Viagens |
| Responsável por tipo de pendência | tipo → pessoa | `SEM_CONTRATO` → Diego |
| Parâmetro ou flag | campo tipado com limites | tolerância de spread, spread negativo em divergências |

- **`REQUER_IMPLEMENTACAO`.** Se a regra pedida é de **cálculo** nova (por exemplo, "antecipação passa a ter piso"), a pessoa usa "Solicitar nova regra" e descreve em texto. O sistema registra a solicitação para o time técnico, mantém o item com o tratamento seguro e não altera nenhum número. Quando o time implementa e libera, a regra entra na lista acima.

---

## 9. Execução em outubro (reuso sem retrabalho)

| Risco de mudança | Mitigação |
|---|---|
| Cabeçalho da planilha desloca de linha | Cabeçalho achado por texto (7.1). |
| Lojista novo ou EC novo | `ENTIDADE_NAO_RESOLVIDA`, e a resposta humana grava alias ou EC em `lojistas_extra.yaml`. |
| Tarifa zero da Casa vence em dezembro | Override com `vigencia_fim` em `config/regras.yaml`, não em código. |
| Layout muda (coluna renomeada) | Falha explícita com o nome da coluna ausente (P9). |
| Transferência de 300 mil cai em 01/10 | Pendência `CONFERIR_OUTUBRO` do mês anterior é carregada como verificação. |
| Rota e Bridge voltam ao normal | Resolvedor usa vigência por data, então segue valendo. |

**Uso mensal pela analista:** abre a interface, clica em "Novo fechamento", escolhe 2026-10 e sobe os arquivos (15.3). O resto do ciclo é o das seções 15.4 a 15.8. As regras aprendidas em setembro já estão no banco, então outubro nasce com menos itens na fila.

**Modo sem interface (reprodutibilidade e correção automática):** `python -m tarvo fechar --mes 2026-10 --dados dados/ --saida saida/`. Usa o mesmo motor e as mesmas regras e decisões do banco (ou os defaults, se o banco estiver vazio), e gera os mesmos arquivos.

---

## 10. Estratégia de verificação

Os números abaixo já foram conferidos à mão contra os dados (`HIPOTESES.md`, memória do projeto). Viram testes de regressão ("golden").

| Teste | Esperado |
|---|---|
| Orbe: truncagem | 1.943 de 1.943 linhas batem com truncagem do `valor_taxa`; zero divergência de R$ 0,01 |
| Orbe: contagem | 290 transações; linhas do mês conforme `00_LEIA-ME` |
| Ponte: dedup | 233 linhas no relatório; `PC-0926-0162` conta 1x |
| Ponte: negativos | 4 operações (`-0210`, `-0326`, `-0491`, `-0545`); desvio contra o contrato Σ R$ 3.565,98 |
| Remessa Mundo Aberto | excesso R$ 1.418,85 (fórmula R10) |
| Casa do Estudante | cobrado indevido ≈ R$ 15,4 mil; comissão checkout negativa; sem nota |
| Rota Global | débito e Pix **sem** divergência; crédito, 2–6x e 7–12x com +0,50 p.p. |
| Aurora | cadeia de saldos fecha em setembro |
| Totais Fox | 214.558,33 / −7.108,69 / 30.491,41 / −6.060,69 (conferidos) |
| Totais Lucca | 39.543,45 e 3.565,98 (conferidos) |
| Invariantes I-R1 a I-D1 | seção 7.9, em todas as execuções |
| Propriedade | permutar a ordem das linhas de entrada não altera as saídas |
| Sem IA | com chave de API ausente, as 6 saídas ainda são geradas e válidas |
| Paridade interface × CLI | rodar o mesmo mês pela interface e pela CLI gera `saida/` idêntica |
| Reprocessamento parcial | uma decisão de classificação reexecuta só as etapas 7 e 9; as demais permanecem com o mesmo checkpoint |
| Upload | cada um dos 6 arquivos do data pack é aceito no seu formato (15.3); arquivo no campo errado, extensão inesperada e coluna ausente geram mensagem clara, sem rodar |
| Configurações | alterar uma regra gera nova versão com autor, motivo e valor anterior; a simulação não grava nada; reverter restaura o resultado anterior |
| Download | os arquivos baixados são byte a byte iguais aos de `saida/` |
| Nada some em silêncio | mês sem dados falha; linha da Ponte sem `PC-` mas com CNPJ ou Spread R$ falha; linha da planilha sem nome mas com CNPJ ou taxa falha; rodapé real (2 linhas na Ponte, 1 na planilha) é contado no log; I-R3 vale em toda execução |

Os números marcados "≈" só viram teste exato depois que o motor existe e o valor é fixado por inspeção manual das linhas de rastro.

---

## 11. Plano de execução (17/10)

Prazos fixos: **Checkpoint 2 às 15h30**, **repo às 18h30**, pitch até 19h. A ordem abaixo respeita "melhor o mínimo certo do que o extra com números que não fecham". Cada bloco termina com os invariantes verdes antes do próximo.

| Bloco | Entrega | Depende de | Linha de corte |
|---|---|---|---|
| **B0** | Esqueleto: `core/money.py`, `ids.py`, `rastro.py`, `excecoes.py`, `writers.py`, validador I-R1 | — | Sem isso nada começa |
| **B1** | Ingestão Orbe + Taxas + registro de lojistas + resolvedor de taxa | B0 | |
| **B2** | **Motor de checkout + comissões + rastro** (nível Mínimo) | B1 | **Nunca cortar. Primeiro commit entregável.** |
| **B3** | Motor de divergências de checkout | B2 | |
| **B4** | Ingestão Ponte (.eml) + motor de remessa + divergências de remessa | B1 | |
| **B5** | Motor de notas | B2, B4 | |
| **B6** | Ingestão Aurora/OFX + plano de contas + classificação por REGRA | B0 | |
| **B7** | Pendências + `quem_decide` + `resumo.md` | B3–B6 | Mínimo viável do Extra |
| **B8** | Orquestrador + `Classificador` + estado (SQLite, eventos por etapa, execução por etapas com checkpoint, fila de exceções) | B6, B7 | Se faltar tempo: só `Classificador` e modo sem IA |
| **B9** | 🖥️ **Interface mínima, já usável:** API + upload com formatos explícitos + executar + workflow ao vivo + fila de validação + saídas com download, com os requisitos U1 a U7 de usabilidade (15.12) | B8 | **Linha de corte da interface (15.11).** Só começa com o B2 verde |
| **B10** | 🖥️ Configurações com simulação de impacto e versionamento, histórico, papéis, drill-down até a linha crua, modo demonstração e demais itens de usabilidade (U8 a U12) | B9 | Corta antes do B9 |
| **B11** | `Investigador`, `InterpreteTaxas` | B8 | **Primeiro a cortar** |
| **B12** | README, `HIPOTESES.md` final, `PROMPTS/MOMENTOS.md`, pitch | — | Começar a escrever às 17h, não às 18h |

Paralelização possível (time de até 3): B4+B5 podem andar em paralelo com B3. B6 é independente de B1–B5. **A casca da interface (B9) pode começar em paralelo assim que o B0 fixar o contrato de eventos e de estado**, usando saídas de exemplo, mas só liga ao motor real depois do B2. A saída oficial para correção continua sendo `saida/`, gerada pela CLI se a interface não ficar pronta.

---

## 12. Pontos a validar com o financeiro (🟡)

Prioridade: **A** = muda número de saída avaliada; **B** = muda classificação ou pendência; **C** = refinamento. O default é o que o código faz hoje. Reversão é a mudança necessária se a resposta for outra.

| ID | Pergunta | Prio | Default no código | Reversão | Quem responde |
|---|---|---|---|---|---|
| **V1** | PIX de R$ 18.240 da Ponte Aérea no Meridiano (MRD2026090425, 17/09) sem operação na Ponte: adiantamento de remessa, duplicidade ou devolução? | B | 2.1.02.001 + pendência | trocar conta; fechar ou manter pendência | Helena |
| **V2** | PIX de R$ 112.220,15 à Atlas em 10/09 (Aurora L34), com R$ 1.247,52 de vendas líquidas até o dia. Foi intencional? Quem autorizou? | B | 2.1.01.001 + pendência de risco | trocar conta | Helena |
| **V3** | Casa do Estudante: (a) estorno TX88445133, de venda de 21/08, abate 1,49% e deixa comissão negativa: confirma "sem nota + pendência"? (b) estornos de vendas de setembro (taxa 0) reduzem o valor a devolver? (c) Casa aparece em `comissoes_por_lojista` com valor negativo ou zero? | **A** | negativa em comissões, sem nota, pendência | `flag` em `regras.yaml` | Helena |
| **V4** | Spread negativo entra também em `divergencias_taxa.csv` (contrato × realizado, Σ R$ 3.565,98) ou só em pendência de contestação? | **A** | entra nas duas | `spread_negativo_em_divergencias: false` | Helena |
| **V5** | Atlas: aparece em `comissoes_por_lojista` (com 0) e em divergências, ou fica totalmente fora? Qual a taxa que vale? Sub-ponto: o `valor_brl` da pendência `SEM_CONTRATO` hoje é a soma da taxa cobrada pela Orbe nas 57 linhas (R$ 7.876,05), só para dimensionar, sem ser valor a faturar. Prefere outro critério? | **A** | totalmente fora; só pendência, com valor = taxa cobrada pela Orbe | liberar quando comercial confirmar a taxa | Diego (comercial) |
| **V6** | `quem_decide` por tipo de pendência (tabela 7.8): Helena versus Diego versus Bia (dona da planilha)? Sub-ponto: granularidade da `DIVERGENCIA_ORBE`. Hoje geramos 1 pendência por divergência (210 em setembro). Prefere 1 por lojista (3 linhas), com as operações listadas no motivo? | B | tabela 7.8; 1 pendência por divergência | editar `regras.yaml` | Helena |
| **V7** | Contas ⚠️ do plano de contas: TED Orbe, PIX lojistas (Aurora e Meridiano), TED Ponte, CDB e rendimento, IOF s/ crédito no Meridiano, tarifa de câmbio, seguro | **A** | tabela 2.5 do `HIPOTESES.md` | editar `plano_contas_regras.yaml` | Helena |
| **V8** | Excesso da Mundo Aberto: usar `Spread %` aplicado (R$ 1.418,85) ou `Spread R$` − 1,2% × ME × PTAX (R$ 1.418,88)? | **A** | R$ 1.418,85 | `formula_divergencia_remessa` | Helena |
| **V9** | Tolerância de 0,01 p.p. no spread de remessa: ok registrar como critério nosso? (ela já aceitou, desde que escrito) | C | 0,01 p.p. | `tolerancia_spread_pp` | Helena |
| **V10** | Comparar divergência de checkout pela **taxa** (2 casas) e não pelo valor em R$: confirma? (a regra do centavo é dela, a forma é nossa) | C | taxa | — | Helena |
| **V11** | Faixas de parcelas: 1x = crédito à vista; 2–6x e 7–12x pelas colunas da planilha; 13x ou mais? | B | pelas colunas; fora da faixa vira exceção | adicionar faixa | Helena |
| **V12** | Devolução de R$ 12.400 da Mundo Aberto (Aurora L65): motivo? Não bate com nenhum PIX enviado | B | 2.1.01.001 + pendência | trocar conta | Helena |
| **V13** | Transferência de R$ 300 mil (L92, 30/09) cai no Meridiano em 01/10: confirmado ✅; só precisa conferir em outubro | C | 1.1.09.001 + `CONFERIR_OUTUBRO` | — | — |
| **V14** | Estornos de vendas de agosto (9 casos, vendas fora do arquivo): taxa da planilha atual na data de agosto está correta para esses lojistas? | B | planilha atual, com `regra_id = C3-HISTORICO` | taxa por exceção em `regras.yaml` | Helena |
| **V15** | Estorno feito a taxa diferente da contratada (ex.: Rota após 12/09) entra como divergência com sinal negativo? | **A** | sim, negativo | `flag` | Helena |
| **V16** | ECs novos em outubro: quem avisa e onde registramos? Hoje há 3 ECs que só o canal conhecia. | C | `lojistas_extra.yaml` | — | Helena, Bia |
| **V17** | Governança na interface: quem pode (a) alterar regras de negócio, (b) decidir pendências financeiras, (c) fechar o mês? Hoje só a Helena decide, a Bia edita a planilha e o Diego responde pelo comercial. | B | 3 papéis: Analista (sobe, roda, valida classificação), Aprovador (decide pendências, altera regras, fecha), Leitor | editar papéis em Configurações | Helena |
| **V18** | Fechamento do mês: depois de "Fechado", pode reabrir? (agosto está fechado e a Helena não reabre ✅) | B | congelado; reabrir só pelo Aprovador, com motivo, gerando nova versão | permitir ou bloquear reabertura | Helena |
| **V0** | Orquestrador LLM versus código (decisão de arquitetura A1) | C | código | trocar `orquestrador.py` | Nosso time |
| **V0b** | Stack da interface (decisão A2): Jinja + HTMX + Tailwind versus React | C | Jinja + HTMX + Tailwind | trocar a camada `web/` | Nosso time |

**Ordem sugerida de envio** (bloco único, até 20h30 de ontem ou 9h30 de hoje, já que o atendimento é limitado): V3, V4, V5, V15, V8, V7, depois V1, V2, V12. As perguntas V1 a V4 são as 4 que nenhum outro time fez (`CHECKPOINTS.md`).

---

## 13. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Resposta do financeiro chega depois de gerar a saída | Número diferente do gabarito | Todos os 🟡 do tipo A são `flags` de uma linha em `regras.yaml`. Regenerar leva segundos. |
| Gabarito trata divergência de remessa ou de Atlas diferente do nosso | Alarme falso | Sempre que houver dúvida sobre incluir ou não, a linha entra em `pendencias.csv` e **fora** de `divergencias_taxa.csv`, exceto onde o financeiro confirmou (✅). V4 e V5 são as duas exceções ⚠️. |
| `ref_origem` repetido dentro do mesmo `id_saida` (venda e antecipação na mesma transação) | Rastro ambíguo | Coluna extra `componente`; a soma por `id_saida` continua correta. |
| Agente erra e ninguém percebe | Número inventado | P2 (IA não calcula), guardrails em código, limiar de confiança, `metodo=IA` visível na saída, e cache versionado para auditoria. |
| Dependência de chave de API durante o pitch | Demo falha | Modo sem IA (8.3) gera as 6 saídas completas. |
| Tempo: construir o Extra e perder o Mínimo | Pior nota possível | Plano da seção 11: B2 primeiro, B9 cortado primeiro. |
| Ordem das linhas ou duplicatas de linha na Orbe | Soma errada | Propriedade de teste (seção 10) e chave única por `id_transacao`. |
| Mês errado ou linha descartada em silêncio | Saídas vazias que parecem válidas, ou comissão que some | Gate de mês, ledger no `execucao.log`, leitores que falham em linha com cara de dado e I-R3 em toda execução (7.1 e 7.9). |
| **A interface consome o dia e o mínimo não fecha** | Pior nota possível: "mockup não conta" e o número correto vale 25% | B9 só começa com o B2 verde. A CLI gera `saida/` com o mesmo motor, então a entrega para correção independe da interface. Cortar B10 e B11 antes de cortar B9. |
| Interface e CLI divergem | Número diferente do mostrado ao financeiro | Uma só implementação do motor, chamada pelos dois. Teste de paridade (seção 10). |
| Usuário edita regra e quebra um fechamento | Número errado sem rastro de quem mudou | Simulação de impacto antes de salvar, motivo obrigatório, versionamento, reversão e parâmetros ✅ travados para o papel Analista (15.7). |
| Upload com arquivo trocado de campo | Número calculado sobre dado errado | Detecção por conteúdo, pré-validação bloqueante (gate G1) e mensagem com a coluna ausente. |
| Polimento da interface sem limite de tempo | O mínimo ou o alvo atrasam | Os requisitos essenciais de usabilidade (U1 a U7) entram no B9 com tempo fixo. Os desejáveis (U8 a U12) só depois do mínimo. |
| Regra de cálculo nova não cabe nos formulários | Usuário acha que "configurou" e nada mudou | `REQUER_IMPLEMENTACAO` explícito (8.5): o item fica marcado e com tratamento seguro. |

---

## 14. O que dizer no pitch sobre IA (para o financeiro e o CFO)

- **Onde a IA atua:** nos casos que nenhuma regra cobre: descrição de extrato sem padrão, texto livre da planilha de taxas, e levantamento de evidências sobre movimentos estranhos.
- **Onde não atua:** em qualquer valor em reais, em qualquer taxa, em nota fiscal. Isso é código com regra confirmada pela Helena.
- **Por quê:** para o número ser reproduzível e rastreável até a linha de origem, e para a IA não decidir regra de negócio que está a uma pergunta de distância.
- **Quando falha:** vira linha em `pendencias.csv`, com motivo e quem decide. A decisão humana vira regra e o próximo mês nasce com menos pendências.
- **Como a analista usa em outubro:** abre a interface, sobe os arquivos, acompanha as etapas, responde só o que o sistema não sabe e baixa as saídas. Quando a regra de negócio muda, ela ajusta na tela Configurações, vê o impacto antes de salvar e a mudança fica registrada com autor e data. Nenhum arquivo técnico.

---

## 15. Interface web 🖥️

### 15.1 Princípios

- **Usuários:** a analista que roda o fechamento e a Helena, que decide as pendências financeiras. Ninguém é técnico (P10).
- **A interface é fina (P11):** não calcula, não decide. Ela chama o mesmo motor da CLI e mostra o que aconteceu.
- **Linguagem do financeiro:** a tela diz "Lojista não identificado", não `ENTIDADE_NAO_RESOLVIDA`. Códigos técnicos aparecem só em detalhe.
- **Usável e apresentável:** a interface é o que o financeiro, o CFO e a banca vão ver no pitch, então precisa ser clara e consistente (15.12). Corretude e rastreabilidade vêm primeiro: cada número é clicável até a linha de origem.

### 15.2 Mapa de telas

| # | Tela | Para quê |
|---|---|---|
| 1 | **Fechamentos** | Lista de meses com status (em andamento, aguardando validação, pronto para fechar, fechado). Botão **Novo fechamento**. |
| 2 | **Upload** | Subir os 6 arquivos do mês, com formatos aceitos explícitos (15.3). |
| 3 | **Pré-validação** | O que o sistema entendeu de cada arquivo antes de rodar (gate G1). |
| 4 | **Workflow** | Acompanhar as etapas do pipeline e a atuação dos agentes, ao vivo (15.4). |
| 5 | **Fila de validação** | Decidir o que o sistema não sabe (15.6). |
| 6 | **Saídas** | Ver as 6 tabelas, abrir o rastro, baixar (15.8). |
| 7 | **Configurações** | Regras e parâmetros de negócio, versionados (15.7). |
| 8 | **Histórico e auditoria** | Quem decidiu ou mudou o quê, quando e por quê. |

### 15.3 Upload e formatos aceitos

A tela mostra, em texto fixo ao lado de cada campo, o formato aceito. Cada campo aceita o formato **exatamente como o arquivo chega** (CSV, XLSX, EML e OFX, conforme o arquivo).

| Arquivo | Formatos aceitos (texto exibido na tela) | Observação |
|---|---|---|
| Orbe: relatório de comissões | `.csv` | Como exportado do portal (`;`, vírgula decimal, datas pt-BR). |
| Taxas contratadas | `.xlsx` | O sistema usa a aba "Taxas vigentes", ignora a aba "ANTIGO" e mostra qual aba usou. |
| Ponte Câmbio: relatório | `.eml` (e-mail com anexo XLSX) | O anexo é extraído sozinho e vale a aba `Operações`. |
| Plano de contas | `.csv` | Só contas analíticas aceitam lançamento. |
| Extrato Aurora | `.csv` | Cadeia de saldos verificada. |
| Extrato Meridiano | `.ofx` | Lido em CP1252, com as tags SGML sem fechamento. |

Regras de comportamento:

- **Detecção por conteúdo, não por extensão.** O sistema acha o cabeçalho pelo texto das colunas e detecta o encoding (UTF-8, Latin-1, CP1252). Se a usuária solta os 6 arquivos de uma vez, ele atribui cada um ao campo certo pela estrutura e avisa quando um arquivo parece estar no campo errado.
- **Sem limpeza manual.** Ela sobe o arquivo como veio. Isso é exigência do brief.
- **Só os formatos em que os arquivos chegam.** Não há conversores para outros formatos. Arquivo com extensão diferente da esperada para aquele campo é recusado com mensagem clara, dizendo qual formato o campo espera.

### 15.4 Workflow ao vivo

A tela do fechamento mostra as etapas na ordem, cada uma com estado (pendente, executando, concluída, com alertas, aguardando validação, erro), duração, linhas lidas e processadas, nº de exceções geradas e link para o detalhe.

| Etapa | Corresponde a |
|---|---|
| 1. Leitura e pré-validação | 7.1 |
| 2. Identidade e contratos | 5 e 7.2 |
| 3. Checkout | 7.3 |
| 4. Remessa | 7.4 |
| 5. Divergências | 7.5 |
| 6. Notas | 7.6 |
| 7. Classificação bancária | 7.7 |
| 8. Exceções e agentes | 8 |
| 9. Consolidação e invariantes | 7.9 |
| 10. Revisão final e fechamento | 15.5, gate G4 |

**Painel de agentes** (dentro da etapa 8 e também na etapa 7): uma linha por chamada, com o agente, a exceção que o acionou, a entrada resumida, a saída, a confiança, o resultado do guardrail (**aceita**, **rejeitada** ou **enviada ao humano**), o tempo, o custo e o orçamento de chamadas restante (`max_chamadas_llm`). A usuária enxerga onde a IA atuou e onde não atuou, que é o que o pitch precisa mostrar.

Os dados vêm da tabela `run_eventos`, entregues por SSE, sem recarregar a página.

### 15.5 Pontos de validação

| Gate | Quando | Bloqueia? | Quem |
|---|---|---|---|
| **G1 Arquivos** | Depois do upload: arquivo faltando, layout inválido, período incompatível com o mês escolhido, cadeia de saldos da Aurora quebrada | **Sim.** Não roda enquanto houver erro estrutural | Analista |
| **G2 Contratos e entidades** | Lojista ou EC novo, contrato ambíguo, vigência lida por agente | Não bloqueia a execução, mas o item sai **provisório** e bloqueia o G4 | Aprovador |
| **G3 Fila de decisões** | Exceções que o motor e os agentes não resolveram (15.6) | **Não** para a execução. Cada decisão reprocessa as etapas afetadas | Quem a fila indicar |
| **G4 Revisão final e fechamento** | Resumo com totais por linha de negócio, dinheiro em jogo, pendências e invariantes. Só libera sem item bloqueante provisório | **Sim.** Fechar congela as saídas e as decisões usadas (snapshot) | Aprovador 🟡 V17, V18 |

### 15.6 Fila de validação

Cada exceção é um cartão com:

- contexto em linguagem de negócio, valor e data;
- **evidências**, cada uma com link para o rastro e para a linha crua do arquivo de origem;
- proposta do agente, com confiança e justificativa (quando houve agente);
- ações: **Aceitar a proposta**, **Escolher outra opção** (lista fechada, por exemplo só contas analíticas), **Encaminhar** a outra pessoa, ou **Solicitar nova regra** (texto livre, vira `REQUER_IMPLEMENTACAO`, 8.5);
- **escopo** (obrigatório): "só neste caso" ou "sempre que acontecer";
- **prévia de impacto**: "isto afeta 3 lançamentos deste mês e vira regra para os próximos".

Responder grava autor e data e reprocessa só o necessário. Resposta em texto livre **nunca** altera número sozinha.

### 15.7 Configurações (substitui YAML e CSV)

Todo ajuste de regra é feito por formulário tipado, com validação de campo (tipo, intervalo, valores permitidos).

| Seção | O que a usuária faz |
|---|---|
| Lojistas e identificadores | Vê CNPJ, ECs e aliases de cada lojista. Adiciona EC ou alias. Vê o que veio da planilha e o que foi acrescentado à mão. |
| Taxas e vigências | Cria override com vigência (ex.: Casa do Estudante, MDR e antecipação 0%, set a dez). Vê a **taxa efetiva por data**, com a origem (planilha ou override). |
| Classificação bancária | Edita a tabela "padrão de descrição → conta", com seletor só de contas analíticas e botão **Testar** contra o extrato carregado. |
| Responsáveis | Define quem decide cada tipo de pendência (7.8). |
| Parâmetros | Tolerância de spread, fórmula da divergência de remessa, spread negativo em divergências, limiar de confiança e limite de chamadas dos agentes. |
| Agentes | Liga ou desliga cada agente, escolhe modelo e orçamento. |
| Tipos de exceção | Marca cada tipo como bloqueante ou não bloqueante para o fechamento. |

Garantias em toda alteração (P12):

- **motivo obrigatório**, autor, data, valor anterior, vigência opcional e número de versão;
- **Simular impacto**: reprocessa o mês atual em modo simulação e mostra a diferença em comissões, divergências, notas e pendências **antes de salvar**. A simulação não grava nada;
- **histórico e reversão** por versão;
- **parâmetros travados** (cadeado e fonte visíveis): o que é regra confirmada pela Helena (✅), como o arredondamento e o 50% da remessa, só o Aprovador altera, e a tela mostra a fonte da confirmação.

### 15.8 Saídas

- Uma aba por saída (as 6) mais o resumo. Cada tabela tem busca, filtro e ordenação.
- Cada linha tem o selo **"reconcilia"** quando Σ do rastro = valor. Linha com exceção provisória mostra o selo **provisório**.
- **Drill-down em três níveis:** valor da saída → linhas de rastro (com `regra_id`) → linha crua do arquivo de origem, exibida como veio.
- Pendências filtráveis por tipo e por `quem_decide`.
- **Download:** cada CSV no formato do contrato (`;`, `.` decimal, `AAAA-MM-DD`, CNPJ com 14 dígitos), um ZIP com todos, e o resumo. O que se baixa é byte a byte o conteúdo de `saida/`.

### 15.9 Papéis e auditoria

| Papel | Pode |
|---|---|
| Analista | Subir arquivos, executar, validar classificações e entidades, baixar |
| Aprovador | Tudo do Analista, mais decidir pendências financeiras, alterar regras e parâmetros travados, fechar e reabrir o mês |
| Leitor | Ver e baixar |

Para o hackathon, a identificação é uma seleção simples de usuário, sem senha, mas toda ação grava o autor. Todo evento (upload, execução, decisão, mudança de regra, fechamento) entra no log de auditoria. 🟡 V17.

### 15.10 Arquitetura técnica da interface

| Endpoint | Função |
|---|---|
| `POST /fechamentos` | cria o fechamento do mês |
| `POST /fechamentos/{id}/arquivos` | recebe um arquivo, detecta o tipo e valida (G1) |
| `POST /fechamentos/{id}/executar` | inicia o pipeline em segundo plano |
| `GET /fechamentos/{id}/eventos` | SSE com o progresso das etapas e as chamadas dos agentes |
| `GET /fechamentos/{id}/fila` e `POST .../decisoes` | lista e responde a fila de validação |
| `POST /fechamentos/{id}/fechar` | gate G4: congela o snapshot |
| `GET/PUT /config/{secao}` e `POST /config/simular` | regras versionadas e simulação de impacto |
| `GET /fechamentos/{id}/saidas/{nome}` e `.../download` | consulta e download |

**Reprocessamento parcial.** Cada etapa persiste seu resultado em `data/execucoes/<id>/`. Existe um mapa fixo de dependências, por exemplo: decisão de classificação → refaz as etapas 7 e 9; override de taxa → refaz 3, 5, 6 e 9; alias de lojista → refaz 2 em diante. Isso evita rodar tudo de novo a cada resposta e mantém o resultado reproduzível (P8).

### 15.11 Prioridade e linha de corte da interface

| Prioridade | Conteúdo | Telas |
|---|---|---|
| **MVP da interface (B9)** | Upload com formatos explícitos, pré-validação, executar, workflow ao vivo com painel de agentes, fila de validação, saídas e download, com a usabilidade essencial (U1 a U7) | 1, 2, 3, 4, 5, 6 |
| **Depois (B10)** | Configurações com simulação e versionamento, histórico e auditoria, papéis, drill-down até a linha crua | 7, 8 e extras da 6 |

Enquanto a tela de Configurações não existir, a promoção "sempre que acontecer" da fila (15.6) já grava a regra no banco, e os defaults de fábrica cobrem o resto. A CLI funciona em todos os cenários e é a rota de entrega garantida para a correção automática.

### 15.12 Usabilidade e demonstração

A interface é o que o financeiro e a banca vão ver no pitch, e parte da nota é explicar a solução a quem não é técnico. Por isso a usabilidade é requisito, com a corretude dos números sempre à frente.

**Essenciais (entram no B9):**

| # | Requisito |
|---|---|
| U1 | **Fluxo guiado em passos**, sempre visível: Arquivos → Conferência → Execução → Validações → Saídas → Fechar. A usuária sabe onde está e o que falta. |
| U2 | **Uma ação principal por tela**, com botão de destaque. Telas vazias dizem qual é o próximo passo. |
| U3 | **Erros em linguagem de negócio, com o que fazer.** Exemplo: "Falta a coluna CNPJ na aba Taxas vigentes. Suba a planilha de novo." Nada de stack trace. |
| U4 | **Progresso ao vivo** por etapa, sem tela travada nem recarga manual. |
| U5 | **Painel-resumo no topo do fechamento:** comissão de checkout, comissão de remessa, nº e valor das divergências, notas a emitir, pendências abertas por quem decide, e o selo "tudo reconcilia". |
| U6 | **Formato brasileiro na tela** (R$ 1.234,56 e dd/mm/aaaa). Os arquivos baixados seguem o contrato (ponto decimal e AAAA-MM-DD). A tela nunca mostra um formato e baixa outro sem avisar. |
| U7 | **Fila de validação enxuta:** contexto em uma frase, valor, 2 a 3 botões. Itens iguais podem ser decididos de uma vez ("aplicar aos 5 lançamentos iguais"). |

**Desejáveis (B10, só depois do mínimo):**

| # | Requisito |
|---|---|
| U8 | Drill-down em painel lateral, sem trocar de página. |
| U9 | Na simulação de impacto, comparação antes e depois em duas colunas. |
| U10 | **Modo demonstração:** carrega setembro/2026 com um clique a partir do data pack, para o pitch não depender de upload ao vivo. |
| U11 | Identidade visual consistente (paleta, tipografia, componentes) e acessibilidade básica: contraste e foco de teclado. |
| U12 | Layout para notebook e projetor (1366×768 e 1920×1080). Mobile não é requisito. |

**Roteiro da demonstração no pitch** (cerca de 4 a 5 minutos dos 15), que também serve de teste de aceitação:

1. Novo fechamento de setembro/2026. Arrastar os 6 arquivos de uma vez, e cada um cai no campo certo.
2. Pré-validação: o sistema mostra a operação duplicada da Ponte e a cadeia de saldos da Aurora fechando.
3. Workflow ao vivo: etapas andando e painel de agentes mostrando em quantos casos a IA atuou e quantos foram a humano.
4. Fila de validação: responder uma pendência com "sempre que acontecer" e ver a prévia de impacto.
5. Saídas: clicar numa comissão, abrir o rastro e chegar à linha da Orbe.
6. Dinheiro em jogo (Casa do Estudante, Rota Global, Mundo Aberto, spreads negativos) e download dos arquivos.

**Teste de usabilidade:** um membro do time que não construiu a tela executa os passos 1 a 6 sem ajuda e cronometrado. O que travar entra na lista de correções do B9.
