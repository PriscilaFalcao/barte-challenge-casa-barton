# Checkpoints

## Checkpoint 1 (até 11h, 17/10)

### O que vamos atacar

Fechamento de set/2026 da Tarvo direto dos arquivos como chegam. Todo número tem rastro até a linha de origem.

1. **Mínimo (primeiro, sem pular):** comissão de CHECKOUT por lojista, calculada pela taxa contratada linha a linha, com estornos, antecipações e reversões. Inclui `rastro.csv` fechando centavo a centavo.
2. **Alvo:**
   - Comissão de REMESSA: 50% do spread realizado, sem a duplicata e sem os spreads negativos.
   - Divergências de taxa transação por transação, nas duas linhas.
   - Notas a emitir: uma por lojista no checkout e uma para a Ponte na remessa.
   - Classificação dos dois extratos no plano de contas, por regra e com confiança.
3. **Extra:**
   - `pendencias.csv` com motivo e quem decide.
   - Leitura robusta de formato, para rodar em outubro sem mexer no código.

### Principais hipóteses

**Por que o fechamento é lento e erra** (detalhe e evidência em `HIPOTESES.md`):

- **H1. Falta de chave comum entre as fontes.**
  - Orbe → planilha casa só 85% das linhas pelo EC.
  - Ponte → planilha só casa depois de normalizar o CNPJ (103 de 233 sem normalização).
  - Extratos bancários não trazem CNPJ dos lojistas.
- **H2. Relatórios de parceiros aceitos sem conferência.**
  - Ponte: a operação duplicada entra no total; 4 spreads negativos; Mundo Aberto a 1,5% contra 1,2% contratado.
  - Orbe: cobra fora do contrato da Rota, da Bridge e da Casa do Estudante.
- **H3. Regras fora da planilha, espalhadas entre financeiro, comercial e quem edita a planilha.** Exemplos: tarifa zero da Casa, Atlas sem contrato, valor do spread "padrão".
- **H4. Sem histórico.** Contratos não são versionados, divergências passadas não são registradas e não existe agenda de recebíveis.

**Dinheiro em jogo já identificado em setembro** (valores preliminares):

| Caso | Valor |
|---|---|
| Casa do Estudante, cobrada sem dever | ≈ R$ 15,4 mil |
| Mundo Aberto, spread a mais | ≈ R$ 1,4 mil |
| Rota Global, +0,5 p.p. no crédito | ≈ R$ 1,5 mil |
| Spreads negativos contra o contrato | ≈ R$ 3,6 mil |
| Duplicata, que inflaria a nossa parte | R$ 411 |
| PIX sem operação | R$ 18,2 mil |
| Repasse à Atlas em 10/09, no 1º dia, com R$ 1,2 mil de vendas | R$ 112 mil |

**Premissas-chave nossas** (onde o financeiro deixou a decisão conosco):

- Divergência de checkout comparada **na taxa**, não no valor. A Orbe trunca centavos; comparar valores geraria cerca de 1.000 alarmes falsos de R$ 0,01.
- Tolerância de 0,01 p.p. no spread de remessa: o ruído observado é de ±0,0016 p.p.
- Spread negativo entra também como divergência, além de contestação.

### O que fica de fora

- **Conciliação Orbe × banco parcela a parcela.** Falta a agenda de recebíveis, e o financeiro confirmou que não precisa neste fechamento. Classificamos as TEDs.
- **Faturar a Atlas ou apontar divergência dela.** Não há contrato; ela vai para pendência do comercial.
- **Decidir devoluções e contestações.** Entregamos os casos com valor e transação; quem decide é o financeiro.
- **Interface visual.** A saída são os CSVs do formato pedido mais um resumo legível.
- **Reconciliar meses anteriores** (jul/ago), por falta de dados.

### Próximos passos

- Enviar ao financeiro 4 perguntas que nenhum time fez: o PIX de R$ 18.240, o repasse à Atlas, o estorno de agosto da Casa e o spread negativo como divergência.
- Implementar o mínimo e validar os totais contra as linhas de origem antes de passar para o alvo.
