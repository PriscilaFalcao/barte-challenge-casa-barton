# Hipóteses e premissas: fechamento Tarvo, setembro/2026

## 0. Como ler este documento

Cada item tem um status:

| Status | Significado |
|---|---|
| ✅ CONFIRMADO | Regra dada pelo financeiro da Tarvo (Helena) no canal, com o time que perguntou e o horário. |
| 📄 FATO DOS DADOS | Verificado diretamente nos arquivos de `dados/`, com o ID ou a linha de origem. |
| ⚠️ PREMISSA NOSSA | Decisão nossa onde não há regra. Traz o motivo, o efeito no número e como reverter. |
| ❓ EM ABERTO | Pergunta ainda sem resposta. Enquanto isso, vale a premissa indicada. |

Todas as contas foram conferidas em decimal exato, sem tolerância (ver `PROMPTS/MOMENTOS.md`, momento 1).

---

## 1. Hipóteses de causa raiz: por que o fechamento é lento e erra

Cada hipótese foi verificada duas vezes contra os dados. A coluna "veredito" diz o que sobreviveu.

### H1. Falta de chave comum entre as fontes

**Veredito: confirmada em parte, com reformulação.** A chave existe entre os sistemas de parceiros, mas está incompleta e sem padrão. Entre os bancos e as operações, ela não existe.

| Ligação | Chave | Cobertura verificada |
|---|---|---|
| Orbe → planilha | `cod_estabelecimento` = `EC Orbe` | 1.653 de 1.943 linhas (85%). Com o mapeamento que a Helena deu no canal, 1.886. As 57 da Atlas não têm cadastro. |
| Ponte → planilha | CNPJ | 233 de 233 **depois de normalizar**. Sem normalizar, só 103 batem: o CNPJ vem com máscara, sem máscara e até como número sem o zero à esquerda (Fluente, Campus Global). |
| Orbe (nome) | — | O mesmo EC aparece com até 3 grafias (9 grafias extras no mês). Quem casa pelo nome erra. |
| Aurora → lojista | **nenhuma** | Os PIX enviados trazem só o nome truncado em cerca de 37 caracteres. Os únicos CNPJs no histórico são o da Orbe e o do PIX sem identificação (L50). |
| Aurora → Orbe | **nenhuma** | As TEDs da Orbe (21, R$ 3.557.246,29) não batem com o líquido diário. A liquidação segue a agenda de parcelas, que não veio no pacote. |
| Meridiano → Ponte | só por soma | A TED do dia = Σ(Valor R$ + IOF) das operações contratadas naquele dia. Não há número da operação no extrato. |
| Meridiano → lojista | **nenhuma** | Nome truncado, com acento inconsistente ("PONTE AÉREA" e "PONTE AEREA"). |

**Por que importa:** a analista precisa casar fontes "no olho". Sem chave, a duplicata da Ponte e o PIX de R$ 18.240 só aparecem cruzando somas por lojista.

### H2. O relatório da Ponte é aceito sem validação

**Veredito: confirmada, e vale também para a Orbe.** Nenhum relatório de parceiro é conferido contra o contrato ou contra o banco.

- **Ponte (📄):**
  - A operação `PC-0926-0162` está duplicada, e o rodapé (233 operações, R$ 78.073,59) e a aba Resumo **contam a duplicata**. Aceitar o total infla a nossa parte em R$ 410,94. O banco prova que a operação repetida não existe: a Bagagem Livre enviou exatamente R$ 55.811,47 a menos que o relatório.
  - Há 4 spreads negativos que o relatório soma normalmente.
  - A Mundo Aberto é cobrada a 1,5% contra 1,2% contratados desde julho (✅ Helena: "a Ponte já devia estar aplicando").
- **Orbe (📄):**
  - Rota Global: +0,50 p.p. no crédito desde 12/09, quando o contrato não mudou (✅).
  - Bridge: 2,59% em 5 vendas que já deveriam estar a 2,19%.
  - Casa do Estudante: cobrada normalmente, mas a tarifa é zero (✅ "ninguém avisou a Orbe").
- **Depoimento do financeiro:** "às vezes vem operação repetida, às vezes vem spread negativo, e eu não sei se aceito"; "ainda não contestei nada"; "um lojista reclamou que pagou taxa a mais […] a gente só descobriu porque ele reclamou".

### H3. As regras não estão escritas e só existem na memória da equipe

**Veredito: confirmada, mas com correção.** O conhecimento não está com **uma** pessoa só. Está **espalhado** entre o financeiro, o comercial e quem edita a planilha, e nem a Helena tem tudo.

- **📄 A planilha não traz:**
  - a tarifa zero da Casa (só um comentário: "conversar com Diego (comercial)");
  - o EC de Novo Horizonte, Horizonte Viagens e Kiwi;
  - o valor do spread "padrão" (só o rodapé "spread em branco = padrão");
  - a regra de estorno, a trava de 2h, a competência da remessa e o arredondamento.
- **✅ Partes que só o comercial sabe:** a condição da Casa (Diego) e a taxa da Atlas. Sobre a Atlas, a Helena diz: "não sei qual taxa vale".
- **✅ A Helena também não conhece tudo:** "A Atlas na aba de 2025 eu não sabia. Essa planilha passa por várias mãos." A planilha tem dono declarado ("última atualização: 02/09 - Bia"), mas não tem processo de atualização.
- **Depoimento:** "Tem regra que só eu sei. Se eu sair de férias, o mês não fecha."

### H4. Não há histórico confiável dos dados

**Veredito: confirmada para os termos de contrato e para os fechamentos anteriores.** Fica a ressalva de que o pacote, por desenho do case, traz um mês só. Separamos o que é limitação do case do que é falha da operação.

- **Falha da operação (📄):**
  - A planilha não versiona os contratos: sobrescreve ou acrescenta linha ("Bridge Idiomas (NOVA)"). A renegociação da Mundo Aberto existe só como Obs ("spread negociado em jul/26"), sem a taxa anterior. A aba "ANTIGO 2025" não tem datas. Por isso não dá para saber a taxa de uma data passada sem perguntar.
  - Não há registro de divergências anteriores. A da Mundo Aberto vem desde julho e só agora apareceu, e julho e agosto já estão fechados (✅ "agosto já está fechado e não reabro").
  - Não existe agenda de recebíveis da Orbe (✅ "quando tivermos a agenda de recebíveis"), então não dá para conciliar a Orbe contra o banco.
  - A Atlas começou a operar em 10/09 sem contrato registrado.
- **Limitação do case (📄):**
  - 9 estornos referenciam vendas de agosto que não estão no arquivo; usamos a taxa que estava vigente na data da venda.
  - O OFX do Meridiano não tem saldo inicial.
  - O repasse de agosto da Ponte (R$ 61.884,12) não tem relatório para conferir.

**Síntese:** o fechamento é lento porque cada fonte é casada à mão, sem chave (H1). Erra porque ninguém compara o que os parceiros cobram com o contrato (H2), porque o contrato vigente não está escrito num lugar só (H3) e porque não há registro do que valia antes nem do que já deu errado (H4). Automatizar a planilha como ela é repetiria os quatro problemas.

---

## 2. Regras de negócio

### 2.1 Comissão de checkout

| ID | Regra | Status | Fonte |
|---|---|---|---|
| C1 | Comissão = valor bruto × taxa **contratada**, linha a linha. O `valor_taxa` da Orbe não é a base. Taxa inteira, sem descontar custo da Orbe. | ✅ | Fox AI 20h01; Fox AI 22h20 |
| C2 | Arredondamento comum para o centavo em cada linha (meio centavo para cima; −0,005 vira −0,01), depois soma. A Orbe trunca; a Tarvo não trunca. | ✅ | Fox AI 21h07 |
| C3 | Estorno abate a comissão do mês do estorno, inclusive estorno de venda de agosto, pela taxa que valia na data da venda original. | ✅ | MN AI 20h04 |
| C4 | Antecipação: bruto × taxa de antecipação contratada, na mesma comissão e na mesma nota. A reversão anula só a taxa da antecipação revertida (via `id_referencia`). | ✅ | MN AI 20h26 |
| C5 | Faixa de parcelas: 1x = crédito à vista; 2–6x e 7–12x pelas colunas da planilha (`qtd_parcelas`). | ⚠️ | Leitura direta das colunas da planilha |
| C6 | Vigência da taxa: vale a data da venda (`data_movimento` da VENDA; `data_venda_original` do estorno). A Bridge muda o crédito à vista para 2,19% em vendas a partir de 15/09. | ✅ | MN AI 20h04 ("taxa que valia na data da venda") |
| C7 | Mapeamento dos ECs: 1043300981 = Novo Horizonte (66564512000199); 1043396662 = Horizonte Viagens (78576234000179); 1038867654 = Kiwi (07752116000126). | ✅ | Fox AI 20h16 |
| C8 | **Casa do Estudante:** taxa contratada = 0 (MDR e antecipação) de setembro a dezembro. A remessa segue normal. | ✅ | Lucca 20h36 |
| C9 | **Atlas Idiomas** (EC 1076801732): sem contrato e não faturada até o comercial confirmar. | ✅ | Fox AI 20h16 |
| C10 | Rota Global: o contrato não mudou em 2026, então a cobrança acima da planilha é divergência. | ✅ | Lucca 20h36 |

### 2.2 Divergências de checkout

| ID | Regra | Status | Fonte |
|---|---|---|---|
| D1 | Divergência = taxa aplicada ≠ contratada. Valor = bruto × (aplicada − contratada), arredondado por linha. | ✅ | Fox AI 21h07 |
| D2 | Diferença de centavo causada pela truncagem da Orbe não é divergência. A comparação é feita na **taxa** (2 casas, exata), não no valor em R$. | ✅ / ⚠️ | Fox AI 21h07. A forma de comparar é nossa. |
| D3 | Devolução ao lojista e cobrança à Orbe são decisão da Helena, caso a caso. Cada divergência vira pendência dela. | ✅ | Fox AI 20h01 |
| D4 | Estornos entram como divergência quando foram feitos a uma taxa diferente da contratada na data da venda original (por exemplo, estornos da Rota de vendas após 12/09). O sinal é negativo: a Orbe já devolveu parte do excesso. | ⚠️ | Consequência de C3 + D1 |
| D5 | **Atlas:** não geramos divergência. Sem taxa contratada, qualquer número seria alarme falso. Fica só como pendência. | ⚠️ | C9 |
| D6 | **Atlas, valor da pendência `SEM_CONTRATO`:** `valor_brl` = soma da taxa cobrada pela Orbe nas 57 linhas do mês (R$ 7.876,05), com rastro linha a linha. É só para dimensionar o que está parado, não é valor a faturar nem comissão. A comissão não é calculada. Convenção nossa, não regra do financeiro. Vai junto com a V5 (PRD seção 12). Outros critérios possíveis: volume bruto, ou zero. Nenhum deles muda comissão, nota ou divergência. | ⚠️ | C9, D5 |
| D7 | **Granularidade da pendência de divergência de checkout:** 1 pendência `DIVERGENCIA_ORBE` por divergência (210 em setembro), cada uma com 1 linha de rastro. Coerente com D3 ("cada divergência vira pendência dela") e com a rastreabilidade linha a linha, mas a escolha do nível de detalhe é nossa. Vai como sub-ponto da V6 (PRD seção 12). Alternativa: 1 por lojista, com as operações no motivo. Não muda comissão, nota nem divergência. | ⚠️ | D3 |

### 2.3 Remessa

| ID | Regra | Status | Fonte |
|---|---|---|---|
| R1 | Comissão = 50% do `Spread R$` **realizado**, por operação, arredondado (ex.: 262,01 → 131,01). | ✅ | MN AI 20h30; Fox AI 21h07 |
| R2 | Spread contratado: célula em branco ou "padrão" = 1,5% sobre a PTAX de referência. A base do `Spread %` é Valor ME × PTAX. | ✅ / 📄 | MN AI 20h30; conferido nas 233 linhas |
| R3 | Mundo Aberto: contrato de 1,2%. A cobrança de 1,5% é divergência pelo **valor cheio**, contestada com a Ponte. | ✅ | MN AI 20h30; Fox AI 20h52 |
| R4 | A nota de setembro sai pelo realizado, **incluindo** o excesso da Mundo Aberto. O ajuste vem no mês em que a Ponte devolver. | ✅ | Theo Garcia 21h16 |
| R5 | Spread negativo ("Taxa travada no pedido (D-1)"): fora da comissão e da nota; contestação. | ✅ | MN AI 20h30 |
| R6 | Número de operação é único: a duplicata conta uma vez e entra na lista para a Ponte corrigir o relatório. | ✅ | MN AI 20h30; Insper AI 22h04 |
| R7 | O status "APROVADO C/ RESSALVA" não muda nada. | ✅ | MN AI 20h30 |
| R8 | Competência = data de contratação. As 6 operações contratadas em 30/09 e liquidadas em 01/10 entram em setembro. | ✅ | MN AI 20h30 |
| R9 | Nada foi contestado ainda e estamos no prazo. Não assumir desconto no repasse. Divergências e negativos ficam como pendência de contestação, com valor e operações. | ✅ | Lucca 21h56; Insper AI 22h04 |
| R10 | Valor da divergência de remessa = Valor ME × PTAX × (`Spread %` aplicado − contratado), por operação, arredondado. | ⚠️ | Mesma forma que D1, proposta pela Fox AI sem objeção. A alternativa (`Spread R$` − contratado × ME × PTAX) dá R$ 0,03 a mais no total da Mundo Aberto. |
| R11 | Tolerância de remessa: só é divergência acima de **0,01 p.p.** | ⚠️ | O `Spread %` oscila ±0,0016 p.p. em todos os contratos (arredondamento da Ponte), e o desvio real da Mundo Aberto é ≈0,30 p.p. O corte separa os dois sem ambiguidade. A Helena aceitou critério nosso, desde que escrito (Fox AI 20h52). |
| R12 | Spreads negativos **também** entram em `divergencias_taxa.csv`, pela diferença entre o spread contratado e o realizado (Σ R$ 3.565,98), além da pendência de contestação. | ⚠️ ❓ | A taxa aplicada é diferente da contratada (definição D1). Se não for o caso, basta remover as 4 linhas. |
| R13 | **Sinal e valor nas pendências de contestação da Ponte (convenção nossa):** a divergência de remessa segue o sinal de D1 (aplicado − contratado). Os 4 spreads negativos dão Σ −R$ 3.565,98 (a magnitude é a conferida pela Lucca). O `valor_brl` da pendência `CONTESTACAO_PONTE` é o mesmo desvio (Mundo Aberto: +R$ 1.418,85 em 23 operações; negativos: −R$ 3.565,98; duplicata: a comissão inflada, R$ 410,94). Uma pendência por operação, como em D7. | ⚠️ | R3, R5, R6, R9 |
| R14 | **Remessa, o que não é decidido pelo código:** operação com status fora de APROVADO / APROVADO C/ RESSALVA (`STATUS_PONTE_DESCONHECIDO`) e CNPJ que não está no cadastro (`ENTIDADE_NAO_RESOLVIDA`) ficam fora da comissão e viram pendência para a Helena. Sem contrato vigente para a data, a comissão é calculada (ela não depende do contrato) e só a divergência fica sem avaliação (`CONTRATO_AMBIGUO`). Hoje nenhum desses casos ocorre em setembro. | ⚠️ | P3 |

### 2.4 Notas fiscais

| ID | Regra | Status | Fonte |
|---|---|---|---|
| N1 | CHECKOUT: uma nota por lojista por mês, no valor da comissão (C1–C4). O tomador é o lojista (CNPJ da planilha). | ✅ | MN AI 20h26 |
| N2 | Comissão zero ou negativa não gera nota; vira pendência da Helena e não passa para o mês seguinte. | ✅ | MN AI 20h26 |
| N3 | REMESSA: uma única nota, com a Ponte Câmbio S.A. (CNPJ 75374179000146) como tomadora, pelo total da nossa participação no mês. | ✅ | MN AI 20h26; e-mail da Ponte |
| N4 | Discriminação: texto simples com o serviço e a competência. | ✅ | MN AI 20h26 |
| N5 | Casa do Estudante: a comissão de checkout fica **negativa** (vendas a 0 e estorno TX88445133, de venda de 21/08, a 1,49% = −R$ 5,50). Sem nota de checkout, com pendência. A remessa da Casa entra normalmente na nota da Ponte. | ⚠️ | Consequência de C3 + C8 + N2 |
| N6 | Atlas: sem nota (C9). | ✅ | |

### 2.5 Classificação dos extratos

Regra geral (✅ Fox AI 21h08): `conta_codigo` é a **contrapartida** do movimento no banco. O que já estava registrado baixa a conta onde estava. Já estavam provisionados: a folha, os tributos de agosto e o repasse da Ponte de 04/09 (✅ Lucca 20h36). Tarifas, aluguel, cloud, assinaturas e serviços entram direto como despesa.

| Padrão da descrição | Conta | Status |
|---|---|---|
| TED RECEBIDA … ORBE ADQUIRENCIA | 1.1.03.001 Recebíveis de adquirente – Orbe | ⚠️ |
| PIX ENVIADO <lojista> (Aurora) | 2.1.01.001 Repasses a lojistas a pagar | ⚠️ |
| TRANSF ENTRE CONTAS P/ BCO MERIDIANO / TED RECEBIDA TARVO – MESMA TITULARIDADE | 1.1.09.001 Transferências entre contas próprias | ⚠️ |
| PAGTO SALARIOS – FOLHA 08/2026 | 2.1.04.001 Salários a pagar | ✅ provisionado |
| GPS INSS / GRF FGTS | 2.1.04.002 / 2.1.04.003 | ✅ provisionado |
| PAGTO ISS / DARF 0561 IRRF / DARF 8109 PIS / DARF 2172 COFINS | 2.1.03.003 / .004 / .001 / .002 | ✅ provisionado |
| BOLETO CONDOMINIO | 4.2.02 Aluguel e condomínio | ✅ despesa direta |
| DEB AUT AMAZON WEB SERVICES | 4.2.03 Cloud e infraestrutura | ✅ despesa direta |
| CARTAO PJ – GOOGLE WORKSPACE | 4.2.04 Softwares e assinaturas | ✅ despesa direta |
| PIX ENVIADO CONTABILIDADE EXATA | 4.2.06 Serviços contábeis e jurídicos | ✅ despesa direta |
| TAR … / TARIFA MANUTENCAO / TARIFA PACOTE CAMBIO | 4.2.01 Tarifas bancárias | ✅ despesa direta |
| SEGURO EMPRESARIAL | 4.2.05 Seguros | ✅ despesa direta |
| PIX RECEB <lojista> (Meridiano) | 2.1.02.001 Recursos de lojistas para remessas | ⚠️ |
| TED ENVIADA PONTE CAMBIO SA LIQ OPERACOES | 2.1.02.001 (baixa dos recursos) | ⚠️ |
| TED RECEB PONTE CAMBIO SA REPASSE COMISSAO 08/2026 | 1.1.03.002 Comissões a receber – câmbio | ✅ provisionado |
| APLICACAO / RESGATE AUTOMATICO CDB DI | 1.1.02.001 Aplicação automática Meridiano | ⚠️ |
| RENDIMENTO APLIC AUTOMATICA | 3.2.01 Rendimentos de aplicações | ⚠️ |
| IOF S/ OPERACAO CREDITO | 4.3.01 IOF | ⚠️ (estranho na conta de câmbio, porque a conta garantida está no Aurora) |
| PIX RECEBIDO 38686002000180 SEM IDENTIFICACAO (L50) | 1.1.09.002 Créditos não identificados + pendência | ✅ "não é receita" |
| DEVOLUCAO PIX – MUNDO ABERTO (L65) | 2.1.01.001 (o repasse volta a ser devido) + pendência | ⚠️ ("repasse que voltou", ✅ Lucca 20h36) |
| PIX RECEB PONTE AEREA R$ 18.240 (MRD2026090425) | 2.1.02.001 + pendência | ⚠️ ❓ |

- **`metodo`/`confianca` (⚠️):**
  - REGRA, com confiança 1,0, quando a descrição casa com um padrão inequívoco da tabela.
  - IA só para descrições que nenhuma regra cobre, com confiança < 1.
  - Abaixo de 0,8, ou quando a contrapartida depende de uma decisão (as três linhas com pendência), vira HUMANO e entra em `pendencias.csv`.
- **Orbe × banco:** não conciliamos parcela a parcela (✅ Insper AI 22h09). Classificamos as TEDs e registramos a limitação.

### 2.6 Pendências e quem decide (⚠️)

| Tipo | Quem decide |
|---|---|
| Divergência de taxa da Orbe (devolver ao lojista / cobrar a Orbe) | Helena (financeiro) |
| Contestação com a Ponte (Mundo Aberto, spreads negativos, duplicata) | Helena (financeiro) |
| Casa do Estudante (devolução do cobrado e saldo negativo) | Helena (financeiro), com Diego (comercial) |
| Atlas (taxa e faturamento) | Diego (comercial) |
| Crédito sem origem, devolução de PIX, PIX sem operação | Helena (financeiro) |
| Conferência do TED da Ponte de 06/10 | Helena (financeiro) (✅ Lucca 21h56) |

---

## 3. Inconsistências encontradas

| # | O quê | Evidência | Tratamento |
|---|---|---|---|
| I1 | Orbe trunca `valor_taxa` | 1.943 de 1.943 linhas batem com truncagem; o arredondamento bate em só 942 (ex.: TX88410932: 16,378872 → 16,37) | D2: comparar taxa, não valor |
| I2 | Rota Global +0,50 p.p. desde 12/09 em **crédito à vista, 2–6x e 7–12x**. Débito e Pix não mudaram | 83 vendas; corte limpo entre 11/09 e 12/09. A afirmação no canal de que o débito mudou **não procede** | Divergência; excesso líquido de estornos ≈ R$ 1.546 |
| I3 | Bridge a 2,59% em vendas a partir de 15/09 | TX88428053, TX88429199, TX88428930, TX88429931, TX88431123 (≈ R$ 29,95) | Divergência (C6) |
| I4 | Casa do Estudante cobrada como se a tarifa não fosse zero | 119 lançamentos; ≈ R$ 15,4 mil cobrados | Divergência do valor cobrado (C8) + pendência |
| I5 | Mundo Aberto a 1,5% contra 1,2% | 23 operações (1,4991% a 1,5009%); ≈ R$ 1.418,85 cheio | Divergência + pendência de contestação |
| I6 | PC-0926-0162 duplicada; rodapé e Resumo contam as duas | Linhas 76 e 77 do XLSX diferem só em "reprocessada"; o banco prova R$ 55.811,47 a menos | Conta uma vez + pendência |
| I7 | 4 spreads negativos | PC-0926-0210, -0326, -0491, -0545 (Σ −R$ 1.834,05); nos 4 a observação é "Taxa travada" | R5 + R12 |
| I8 | PIX de R$ 18.240 da Ponte Aérea sem operação | MRD2026090425 (17/09), memo sem acento. Nos outros 13 lojistas, os PIX batem exatamente com Σ(Valor R$ + IOF) | Pendência ❓ |
| I9 | Repasse de R$ 112.220,15 à Atlas em 10/09 (Aurora L34) | No mesmo dia da primeira transação, com só R$ 1.247,52 de líquido na Orbe; 5 antecipações, 2 revertidas | Pendência ❓ (risco) |
| I10 | Devolução de R$ 12.400 da Mundo Aberto (L65) | Não bate com nenhum dos PIX enviados (48.714,59 e 88.746,05) | Pendência |
| I11 | Transferência de R$ 300 mil (L92) sem par no Meridiano | ✅ cai em 01/10 | 1.1.09.001; conferir em outubro |
| I12 | Planilha de taxas | CNPJ em 3 formatos (2 sem o zero à esquerda); taxa como texto ("1,49%") em 2 linhas; vigência em texto livre; Atlas só na aba de 2025; Globo Trotter inativo | Normalização (seção 6) |
| I13 | Fórmula do excesso da Mundo Aberto | 1.418,85 (via `Spread %`) × 1.418,88 (via `Spread R$`) × 1.418,89 (sem arredondar por operação) | R10 |

---

## 4. Perguntas que o nosso time fez ao financeiro

Ainda **nenhuma pergunta enviada** pelo nosso time. As que vamos enviar, sobre o que nenhum outro time perguntou:

| # | Pergunta | Status | Premissa enquanto isso |
|---|---|---|---|
| Q1 | PIX de R$ 18.240 da Ponte Aérea no Meridiano (MRD2026090425, 17/09) sem operação na Ponte. É adiantamento de remessa futura, pagamento em duplicidade ou algo a devolver? | ❓ a enviar | 2.1.02.001 + pendência |
| Q2 | PIX de R$ 112.220,15 à Atlas em 10/09, quando ela tinha R$ 1.247,52 de vendas líquidas. Foi intencional? Quem autorizou? | ❓ a enviar | Pendência para a Helena |
| Q3 | Casa do Estudante: (a) o estorno TX88445133, de venda de 21/08, abate 1,49% e deixa a comissão negativa: confirma pendência sem nota? (b) os estornos de vendas de setembro (ex.: TX88446763) reduzem o valor a devolver? | ❓ a enviar | N5 e D4 |
| Q4 | Spreads negativos: além da pendência de contestação, entram como divergência de taxa, pelo valor contratado contra o realizado? | ❓ a enviar | R12 |

---

## 5. Premissas de formato, para rodar em outubro sem retrabalho (⚠️)

- **Planilha de taxas:**
  - Cabeçalho localizado **pelo nome da coluna** ("Lojista", "CNPJ", "EC Orbe"…), não pelo número da linha.
  - Abas cujo nome contém "ANTIGO" ou "nao usar" são ignoradas.
  - CNPJ: só dígitos, completado com zeros até 14.
  - Taxa: aceita número (`0.0149`) e texto (`'1,49%'`).
  - Vigência: aceita data, "até dd/mm/aaaa" e "a partir de dd/mm/aaaa"; sem vigência = sempre.
  - Lojista com Obs "INATIVO" é ignorado.
  - Linha sem nome de lojista mas com CNPJ, EC ou taxa **falha** (não é tratada como rodapé). Só a nota de rodapé (`*`) e linhas em branco são puladas.
- **Encodings explícitos:**
  - Orbe: ASCII/UTF-8.
  - Aurora: UTF-8.
  - Plano de contas: Latin-1.
  - OFX: CP1252.
- **Ponte:**
  - O anexo `.xlsx` é extraído do `.eml` pelo programa.
  - O cabeçalho é localizado pela célula "Nº Operação".
  - Linhas são de operação quando o ID começa com "PC-". Linha sem esse prefixo que tenha CNPJ, Valor ME ou Spread R$ **falha** (não é tratada como rodapé).
  - Dedup pelo número da operação.
  - O rodapé e a aba Resumo **não** são usados como fonte.
- **Aurora:**
  - `ref_origem` = linha física do arquivo (L9…L92 em setembro).
  - Linhas sem data (SALDO FINAL, aviso) e SALDO ANTERIOR são descartadas.
  - A cadeia de saldos é verificada linha a linha (fecha em setembro).
- **Meridiano:** `ref_origem` = FITID. As tags SGML do OFX não fecham.
- **Nada some em silêncio:**
  - O código só descarta estrutura do arquivo (rodapé, aba ignorada, linha em branco, linha fora do mês), e cada descarte é contado em `saida/execucao.log`.
  - Se nenhuma linha da Orbe nem da Ponte cai no mês pedido, a execução falha (mês errado).
  - Toda linha do mês aparece no rastro (invariante I-R3, verificado em toda execução).
- **Valores pt-BR:** `66.026,00` → 66026.00. Todo cálculo é feito em decimal exato.

## 6. Limitações conhecidas

- **Orbe × banco:** não conciliamos a Orbe contra o banco, por falta da agenda de recebíveis (✅ fora do escopo deste fechamento).
- **Estornos de agosto:** a taxa de estornos de vendas de agosto vem da planilha atual. Se a taxa de agosto fosse outra, a planilha não teria esse histórico (H4).
- **Atlas:** fica fora de comissão, nota e divergências até haver contrato.
- **Casamento por nome nos extratos:** quando necessário, usa o nome normalizado contra a lista fechada de lojistas da planilha, nunca correspondência aproximada aberta. O que não casar exatamente vai para pendência.
