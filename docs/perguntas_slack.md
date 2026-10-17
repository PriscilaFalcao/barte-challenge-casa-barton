Alex Chequer  [19h57]
Boa noite pessoal, o documento diz que as perguntas ao cliente devem ser feitas no canal #tarvo-financeiro, porém ainda não foi criado. Mandamos por aqui memso ou esperamos para criarem esse outro canal?
3 respostasmanuel.freitas  [19h59]
podem enviar aqui. explicitem na thread de duvida se é tarvo ou hackaton
Alex Chequer  [20h01]
Dúvida para a Tarvo:
Fox AI: base da comissão de checkout

Ficamos com uma duvida em relacao ao checkout. Para calcular a comissão de checkout de cada lojista, qual valor devemos usar?

(a) a taxa que a Orbe efetivamente cobrou (valor_taxa do relatório), ou
(b) o valor bruto × a taxa contratada na planilha?

Quando as duas diferem, qual delas vai para a nota fiscal? E a diferença é devolvida ao lojista?
manuel.freitas  [20h05]
A gente fatura pela taxa contratada: valor bruto × taxa da planilha, linha por linha. O valor_taxa do relatório é o que a Orbe cobrou, e nem sempre bate com o contrato.
Na nota fiscal vai a comissão calculada pela taxa contratada.
Quando a taxa aplicada é diferente da contratada, é divergência. Se a Orbe cobrou a mais, a diferença volta para o lojista e eu cobro a Orbe. Isso eu decido, não vai automático. Preciso ver cada caso com transação e valor.



Nader Taha  [20h04]
[financeiro] MN AI: Quando uma venda é estornada, a Tarvo devolve a taxa ao lojista e isso abate a comissão do mês? E se a venda original for de agosto? Ex.: TX88444848 (Oxford Prep, estorno de -R$ 2.193,16 em 01/09 de uma venda de 22/08, taxa -R$ 83,12). Entra em setembro, volta para agosto ou fica fora?
1 respostamanuel.freitas  [20h06]
[Financeiro] Resposta para MN AI
Sim. Estorno devolve a taxa ao lojista e abate a comissão do mês.
Venda de agosto estornada em setembro entra em setembro, que é o mês do estorno. Agosto já está fechado e não reabro. A taxa usada é a que valia na data da venda original.
No exemplo da Oxford Prep, o estorno de 01/09 reduz a comissão de setembro da Oxford, pela taxa contratada que valia em 22/08.


MN AI - murilo godoy  [20h08]
[hackaton] MN AI: Foi comentado sobre o envio de um repositorio seguindo a estrutura passada no documento. Gostaria de saber se podemos criar outros alem desse ou a entrega tem que ser somente em um unico?
1 respostamanuel.freitas  [20h13]
[Logística] Resposta para MN AI
A entrega é um repositório por time. É esse link que vocês mandam por e-mail até 18h30, e é só ele que a banca avalia.
Durante o trabalho vocês podem usar quantos repositórios quiserem, mas o que for entregue precisa ter tudo: código, saida/, PROMPTS/, HIPOTESES.md e um README.md que rode a solução do zero. Se a solução tiver mais de uma parte (por exemplo, um backend e uma tela), coloquem as duas em pastas dentro do mesmo repositório.
Partes que rodam em plataforma online (n8n, Lovable etc.) vão como link no README, com instruções de como testar. A regra das 18h30 vale para tudo: o que mudar depois não conta.



Alex Chequer  [20h16]
[financeiro] Fox AI: 4 ECs da Orbe não estão na planilha de taxas vigente (290 transações em setembro):

- 1043300981 HORIZONTE INTERCAMBIO
- 1043396662 HORIZONTE VIAGENS TURISMO
- 1076801732 ATLAS IDIOMAS
- 1038867654 KIWI EXPERIENCE TURISMO

Quais são o CNPJ e as taxas de cada um? Eles correspondem às linhas "Horizonte Viagens", "Novo Horizonte Intercambio" e "Kiwi Experience" da planilha (que estão com o EC em branco)? A Atlas só aparece na aba de 2025: ela ainda é cliente ativa?
1 respostamanuel.freitas  [20h24]
[Financeiro] Resposta para Fox AI
Boa pegada, o EC dessas três está faltando na planilha:

1043300981 HORIZONTE INTERCAMBIO é a Novo Horizonte Intercâmbio, a linha “Novo Horizonte Intercambio”.
1043396662 HORIZONTE VIAGENS TURISMO é a Horizonte Viagens e Turismo, a linha “Horizonte Viagens”. São duas empresas diferentes.
1038867654 KIWI EXPERIENCE TURISMO é a Kiwi Experience, a linha “Kiwi Experience”.
O CNPJ e as taxas dessas três estão nas linhas delas na aba vigente.
A Atlas na aba de 2025 eu não sabia. Essa planilha passa por várias mãos. O que eu sei é que ela começou a transacionar com a gente em 10/09 e que não tenho contrato assinado dela na vigente. Não sei qual taxa vale. Não fatura a Atlas até o comercial confirmar.
— Helena, financeiro da Tarvo



Nader Taha  [20h26]
[financeiro] MN AI: Pela resposta de vocês, a nota de checkout usa a comissão pela taxa contratada. Qual é a regra fixa para montar as notas todo mês?
(a) CHECKOUT: uma nota por lojista por mês, com valor = vendas − estornos (pela taxa da venda original)? A ANTECIPACAO (bruto × taxa contratada, ex.: AN88444882 da Canguru) entra na mesma nota ou em nota separada? A REVERSAO ANTECIPACAO (ex.: AN88445114 reverte a AN88444915 da Mundo Aberto) só anula a original?
(b) Se o saldo do lojista no mês der zero ou negativo por causa de estornos, não emite? O negativo passa para o mês seguinte?
(c) REMESSA: o e-mail da Ponte fala em "nota fiscal de intermediação" para liberar os 50% do spread. O tomador é sempre a Ponte Câmbio (uma nota pelo total) ou cada lojista?
(d) Existe texto padrão para a discriminação?1 respostamanuel.freitas  [20h47]
[Financeiro] Resposta para MN AI (notas)
(a) Sim. No checkout é uma nota por lojista por mês, no valor da comissão do mês pela taxa contratada, como respondi à Fox AI. Estorno abate pela taxa da venda original, como respondi a vocês antes. A antecipação entra na mesma nota, e a reversão só anula a taxa da antecipação que ela reverte.
(b) Zero ou negativo não emite nota. O negativo não passa para o mês seguinte automaticamente. Eu trato com o lojista, então coloca como pendência para mim.
(c) Na remessa, quem paga a gente é a Ponte. É uma nota só, com a Ponte Câmbio como tomadora, pelo total da nossa participação no mês. Não tem nota por lojista.
(d) Não temos texto padrão. Algo simples com o serviço e a competência resolve.
— Helena, financeiro da Tarvo




MN AI - murilo godoy  [20h30]
[financeiro] MN AI: No checkout vocês faturam pela taxa contratada e a diferença vira divergência. A remessa segue a mesma lógica?
(a) A comissão da Tarvo é 50% do "Spread R$" realizado da Ponte ou 50% de valor × "Spread remessa" contratado na planilha? Quando a Ponte aplica mais que o contratado (ex.: Mundo Aberto, contrato de 1,2%, PC-0926-0011 a ~1,5%), isso é divergência a devolver ao lojista? Quanto vale o "padrão" quando a célula está em branco?
(b) Para cada situação, a regra é fixa (conta / não conta) ou é decisão sua caso a caso?
  - spread negativo com "Taxa travada no pedido (D-1)" (ex.: PC-0926-0210)
  - mesmo Nº de operação repetido, um marcado "reprocessada" (ex.: PC-0926-0162)
  - status "APROVADO C/ RESSALVA"
  - contratada num mês e liquidada no seguinte (ex.: PC-0926-0002, liquidada em 01/10): vale a data de contratação ou a de liquidação?1 respostamanuel.freitas  [20h48]
[Financeiro] Resposta para MN AI (remessa)
(a) Na remessa a lógica é outra. A nossa comissão é 50% do “Spread R$” realizado, como está no e-mail da Ponte. A Mundo Aberto negociou 1,20% em julho e a Ponte já devia estar aplicando, então é divergência, e eu contesto com a Ponte. Célula em branco ou “padrão” é 1,5% sobre a PTAX de referência.
(b) Essas eu já sei responder:

Spread negativo: não aceito. A trava vale 2 horas pelo contrato, e essas passaram do prazo. Fica fora da comissão e da nota, e eu contesto.
Operação repetida: o número da operação é único.
“Aprovado c/ ressalva”: o status de compliance não muda nada para a gente.
Data: vale a data de contratação.
Para o que aparecer fora disso, me digam como vocês tratariam e por quê.
— Helena, financeiro da Tarvo




Lucca Landeiro - Lucca Landeiro  [20h36]
[financeiro] Lucca Landeiro:

1) Rota Global (EC 1074504011): a partir de 12/09 a Orbe passou a cobrar +0,50 p.p. em débito, crédito à vista e 2–6x (2,49/2,99/3,59% → 2,99/3,49/4,09%). A planilha vigente segue com as taxas antigas. Houve reajuste contratual ou é divergência?

2) Casa do Estudante (EC 1018325654): a linha tem a observação "cliente estratégico - ver c/ comercial" e um comentário "conversar com Diego (comercial) sobre condição especial". Existe condição especial valendo em setembro, ou fatura pela taxa da planilha?

3) Competência no extrato Aurora: folha, ISS, INSS, FGTS (identificados como 08/2026), IRRF, PIS e COFINS (sem competência no extrato) foram pagos em setembro. Também entrou em setembro o repasse de comissão 08/2026 da Ponte (MRD2026090132, R$ 61.884,12). Lanço tudo na competência agosto ou setembro?

4) Créditos sem origem clara no Aurora: (a) 16/09 PIX R$ 7.350,00 do CNPJ 38.686.002/0001-80 "SEM IDENTIFICACAO"; (b) 23/09 "DEVOLUCAO PIX - MUNDO ABERTO" +R$ 12.400,00 (enviamos 48.714,59 em 09/09 e 88.746,05 em 24/09); (c) 30/09 transferência de R$ 300.000,00 para o Meridiano sem crédito correspondente no extrato do Meridiano. Vocês sabem a origem desses três, ou ficam como pendência?
2 respostasmanuel.freitas  [20h49]
[Financeiro] Resposta para Lucca Landeiro

Não mudou nada no contrato da Rota este ano.
Existe, sim. A Casa do Estudante tem tarifa zerada no checkout de setembro a dezembro, por acordo do comercial para segurar o cliente. Vale para MDR e antecipação. Remessa segue normal. Ninguém avisou a Orbe, então ela cobrou. O que foi cobrado eu devolvo ao lojista, junto com o comercial.
A folha, o ISS, o INSS, o FGTS e os DARFs são de agosto e já estavam provisionados. O repasse da Ponte de 04/09 é o spread de agosto, que já estava como comissão a receber. Com isso, me diga como você lançaria.
(a) Não sei de quem é o Pix de R$ 7.350. Não é receita até alguém identificar. (b) A devolução é um Pix de repasse que voltou, e ainda não sei o motivo. (c) A transferência saiu do Aurora em 30/09 e cai no Meridiano em 01/10. O que fazer com cada um é decisão sua.
— Helena, financeiro da Tarvo
Lucca Landeiro - Lucca Landeiro  [21h06]
[financeiro] Lucca Landeiro: obrigado! Como eu lançaria:
- Folha, ISS, INSS, FGTS, IRRF, PIS e COFINS de agosto: baixa do passivo provisionado (D Salários a pagar / ISS, INSS, FGTS, IRRF, PIS, COFINS a recolher × C Banco Aurora). Não é despesa de setembro.
- Repasse Ponte 08/2026: D Banco Meridiano × C Comissões de intermediação a receber - câmbio.
- PIX R$ 7.350 sem identificação: D Aurora × C Créditos não identificados, com pendência até identificar.
- Devolução Mundo Aberto R$ 12.400: D Aurora × C Repasses a lojistas a pagar (o repasse volta a ser devido), com pendência para o motivo.
- Transferência R$ 300 mil: D Transferências entre contas próprias × C Aurora em 30/09; em 01/10 fecha com D Meridiano.
Se algo aqui estiver diferente do que vocês fazem, me avisa.




Alex Chequer  [20h52]
[financeiro] Fox AI: valor da divergência de remessa (Mundo Aberto)

Proposta: divergência = (Spread % aplicado − contratado) × PTAX × valor em moeda estrangeira, valor cheio, porque é o que o lojista pagou a mais. Ex.: PC-0926-0011: (1,5007% − 1,20%) × 4,0315 × 2.438,46 = R$ 29,56. No mês, a Mundo Aberto soma R$ 1.418,85 em 23 operações.

1. A divergência é o valor cheio ou só a nossa metade (50%)?
2. Nos outros lojistas, o Spread % oscila ±0,002 p.p. em torno do contratado (ex.: 1,4984% a 1,5015% para quem tem 1,5%). Podemos tratar como arredondamento e não reportar divergência abaixo de 0,01 p.p.?1 respostamanuel.freitas  [20h58]
[Financeiro] Resposta para Fox AI

É o valor cheio. Quem pagou a mais foi a Mundo Aberto, e é o total que eu contesto com a Ponte. A nossa metade é só como a Ponte divide o spread com a gente.
O critério de tolerância é de vocês. Se ele estiver escrito, com o motivo, eu sigo. O que eu preciso é não receber alarme de centavo, e também não deixar passar diferença de verdade.

— Helena, financeiro da Tarvo




Helio Henrique  [21h07]
[financeiro] Fox AI: Arredondamento e cálculo das divergências
Os valores da Orbe são compatíveis com truncamento em duas casas decimais. Ex.: TX88410932, bruto de R$ 608,88 e taxa de 2,69%, informa R$ 16,37; arredondando o produto, seria R$ 16,38.
(a) Para calcular a comissão pela taxa contratada, devemos truncar ou arredondar? Qual regra vale para valores negativos e casos de meio centavo?
(b) Aplicamos esse tratamento em cada operação antes de somar ou apenas no total por lojista?
(c) A divergência de checkout deve ser valor_taxa informado pela Orbe − comissão contratada calculada ou valor_bruto × (taxa aplicada − contratada)? Os critérios podem produzir diferenças de centavos. (d) Nas remessas, calculamos e arredondamos os 50% por operação ou somente depois de somar o spread? Ex.: 50% de R$ 262,01 = R$ 131,005.1 respostamanuel.freitas  [21h13]
[Financeiro] Resposta para Fox AI (arredondamento)
Isso mesmo: a Orbe trunca os centavos. A gente não trunca.
(a) Arredondamento comum para o centavo. Meio centavo vai para cima, e no negativo vale a mesma regra com o sinal: -0,005 vira -0,01.
 (b) Linha por linha, e depois soma.
 (c) Divergência é quando a taxa aplicada é diferente da contratada. Diferença de centavo por causa do truncamento da Orbe não é divergência. O valor da divergência eu quero como valor bruto × (taxa aplicada − contratada).
 (d) Por operação, com o mesmo arredondamento. No seu exemplo, R$ 131,01.
— Helena, financeiro da Tarvo




Helio Henrique  [21h08]
financeiro] Fox AI: Critério para classificar os extratos no plano de contas
Complementando a pergunta sobre competência: nossa dúvida é qual conta usar em conta_codigo, considerando o que já foi registrado anteriormente.
(a) O campo deve representar a contrapartida contábil da movimentação bancária, baixando obrigações e recebíveis já registrados, ou a natureza da receita/despesa?
Exemplos:

Folha 08/2026 paga em setembro: 2.1.04.001 — Salários a pagar ou 4.1.01 — Salários e ordenados?
Comissão 08/2026 da Ponte recebida em setembro: 1.1.03.002 — Comissões de intermediação a receber - câmbio ou 3.1.03 — Receita de intermediação de câmbio?
(b) Podemos considerar salários, tributos, fornecedores e comissões de meses anteriores já apropriados? Qual regra devemos seguir quando o extrato não permite saber se houve essa apropriação?
1 respostamanuel.freitas  [21h14]
[Financeiro] Resposta para Fox AI (plano de contas)
(a) Quero a contrapartida do movimento no banco. Se o valor já estava registrado, o pagamento ou recebimento baixa a conta onde ele estava, e não vira receita ou despesa de novo. Como respondi ao Lucca, a folha, os tributos de agosto e o repasse da Ponte de 04/09 já estavam registrados.
 (b) Além desses, nada estava provisionado: tarifas, aluguel, cloud, assinaturas e serviços entram direto na despesa do mês. Quando o extrato não deixar claro, declarem a premissa no HIPOTESES.md e sigam.
— Helena, financeiro da Tarvo




Theo Garcia - Theo Garcia  [21h16]
[financeiro] Theo Garcia: uma pergunta sobre a nota de intermediação de setembro. Pela sua regra, a nossa participação é 50% do Spread R$ realizado. Na Mundo Aberto, o realizado inclui o excesso de 1,50% sobre o 1,20% contratado (R$ 1.418,85 em 23 operações), que a senhora vai contestar com a Ponte. A nossa metade desse excesso (cerca de R$ 709) entra na nota e na comissão de setembro, ou fica fora até a contestação? Hoje seguimos a sua regra: faturamos pelo realizado e deixamos a diferença como pendência sua, para ajustar se a Ponte devolver.1 respostamanuel.freitas  [21h45]
[Financeiro] Resposta para Theo Garcia
Entra. A nota de setembro sai pelo realizado, porque é o que a Ponte vai repassar para a gente agora. A contestação é um processo à parte. Se a Ponte devolver a diferença para a Mundo Aberto, a nossa metade sai no mês em que o ajuste acontecer.
Deixar como pendência para mim é o caminho certo.
— Helena, financeiro da Tarvo





Lucca Landeiro - Lucca Landeiro  [21h56]
[financeiro] Lucca Landeiro: como estou tratando a remessa, para você validar:
- Spreads negativos (PC-0926-0210, -0326, -0491, -0545): fora da comissão e da nota. Em divergências, listo o valor cheio contra o contrato (R$ 3.565,98) e o impacto na nossa participação (R$ 917,03), que é o que a Ponte descontaria do repasse.
- Duplicata PC-0926-0162: conto uma vez. O relatório da Ponte soma as duas linhas, então o total dela (R$ 78.073,59) gera um repasse R$ 410,94 maior que o devido.
- Resultado: faturo R$ 39.543,45 para a Ponte. Pelo total dela, o TED de 06/10 viria uns R$ 506 menor (917,03 − 410,94). Deixo como pendência para conferir no extrato de outubro.
Faz sentido?1 respostamanuel.freitas  [22h33]
[Financeiro] Resposta para Lucca Landeiro
Número eu não valido. Quem fecha é você, e a banca vai olhar o rastro.
Sobre o raciocínio, duas coisas que eu sei:

Não sei ainda como a Ponte vai pagar, porque a contestação nem foi aberta. Não conte que ela vai descontar nada do repasse.
Conferir o TED quando ele cair é uma pendência boa. Fica comigo.
— Helena, financeiro da Tarvo





João Pedro Lucena [INSPER AI]  [22h04]
[financeiro] [INSPER AI]: O e-mail da Ponte de 02/10 prevê cinco dias úteis para contestação, o que levaria a 09/10. As divergências de Mundo Aberto e os spreads negativos já foram contestados, ou existe uma extensão desse prazo?
Se o prazo estiver vencido, isso altera o tratamento no fechamento ou devemos manter os valores como pendências de recuperação pelo financeiro?
A operação duplicada também precisa ser contestada à Ponte ou basta considerá-la uma única vez no fechamento?1 respostamanuel.freitas  [22h34]
[Financeiro] Resposta para Insper AI (contestação)
Ainda não contestei nada. É para isso que eu preciso do fechamento de vocês. Considerem que estamos dentro do prazo: o fechamento é esta semana.
Mantenham como pendência de contestação, com o valor e as operações, porque é isso que eu mando para a Ponte.
A duplicada vocês contam uma vez no fechamento, e ela também entra na lista para a Ponte corrigir o relatório.
— Helena, financeiro da Tarvo






Gustavo [INSPER AI]  [22h09]
[financeiro] [INSPER AI]: O Aurora apresenta saldo negativo a partir de 09/09, chegando a −R$ 2.289.532,94. Identificamos R$ 3.557.246,29 de créditos da Orbe no extrato.

Qual é o fluxo de liquidação da Orbe para a Tarvo? Todos os repasses entram no Aurora ou existem outras contas, compensações ou pagamentos diretos aos lojistas?

O relatório da Orbe soma R$ 7.264.348,20 em valor líquido, incluindo antecipações e reversões. Como esses movimentos devem ser considerados na conciliação, e quais prazos de liquidação explicam o que entra em setembro ou fica para outubro?
1 respostamanuel.freitas  [22h34]
[Financeiro] Resposta para Insper AI (Aurora e Orbe)
A Orbe deposita tudo no Aurora. Ela não paga lojista direto. Débito e Pix caem no dia seguinte. Crédito e parcelado caem ao longo dos meses seguintes, conforme as parcelas. Por isso o que entra no banco em setembro não bate com o líquido do relatório de setembro.
O saldo negativo é a conta garantida que a gente tem no Aurora para pagar os lojistas antes de a Orbe liquidar.
Conciliar a Orbe contra o banco, parcela por parcela, não é o que eu preciso neste fechamento. Os créditos da Orbe vocês classificam, e o resto fica para quando tivermos a agenda de recebíveis.
— Helena, financeiro da Tarvo





as.pereira.leite  [22h20]
[financeiro] Fox AI: Para fechar a comissão de checkout de setembro precisamos de 3 confirmações, assumimos hipóteses e pedimos validação destas.

1) No relatório da Orbe só vemos a taxa cobrada do lojista (valor_taxa; as vendas somam ~R$ 214,6 mil). A comissão da Tarvo é essa taxa inteira ou ela menos um custo da Orbe? Assumimos que se trata da taxa inteira.

2) Estornos: São 59 estornos (−R$ 7,1 mil de taxa), 9 deles de vendas de agosto (ex.: TX88444848). Os estornos reduzem a comissão de setembro, mesmo os de vendas de agosto? Assumimos que sim.

3) Antecipações: A Orbe traz 38 antecipações (taxa de 2,10%, ~R$ 30,5 mil) e 6 reversões de antecipação (−R$ 6,1 mil). A taxa de antecipação entra na comissão do lojista e na nota fiscal, e a reversão abate? Assumimos que entra e abate.
1 respostamanuel.freitas  [22h34]
[Financeiro] Resposta para Fox AI (checkout)
As três já estão respondidas aqui no canal:

A comissão é a taxa inteira, sem desconto de custo da Orbe, mas pela taxa contratada, e não pelo valor_taxa. Está na resposta que dei para vocês mesmos no começo da noite.
Sim, inclusive os de agosto. Respondi para a MN AI.
Entra na mesma nota e a reversão abate. Respondi para a MN AI, sobre as notas.
— Helena, financeiro da Tarvo


[Logística] Entrega: a solução precisa rodar
Para deixar claro o que é a entrega: além do saida/, a banca precisa conseguir rodar o fechamento pela solução de vocês.
Pode ser uma tela, um fluxo no n8n, um app no Lovable ou um único comando no terminal. O formato é com vocês. O mínimo:

Recebe os arquivos do mês (upload ou pasta). Nada fixo no código para setembro.
Roda tudo com um clique ou um comando.
Mostra o resultado e gera os seis arquivos de saida/.
O README explica como abrir e rodar, e onde configurar a chave de API.
A banca vai rodar a solução com os arquivos do case e comparar com o saida/ entregue. Não avaliamos visual: um comando que funciona vale tanto quanto uma tela.
— Organização


[financeiro] MN AI: Os 4 spreads negativos (PC-0926-0210, -0326, -0491 e -0545) ficam fora da comissão e da nota e entram como contestação, como definiram. Eles também devem aparecer na lista de divergências de taxa (aplicado entre −1,55% e −1,65%, contra 1,4% a 1,5% contratados), ou só como pendência de contestação? Hoje tratamos só como pendência, porque o lojista não pagou a mais.

[Financeiro] Resposta para MN AI (spread negativo)
Para mim, divergência é quando o lojista pagou diferente do contrato. No spread negativo o lojista não pagou a mais. O prejuízo é nosso com a Ponte, então é pendência de contestação. Se quiserem listar também nas divergências, tudo bem, desde que fique claro que é outra natureza.
— Helena, financeiro da Tarvo

Perguntas para a Tarvo:

1 - P3 — Tarifa zerada da Casa do Estudante × divergência (H03, até R$ 15.397,42) Durante a tarifa zerada da Casa do Estudante, a Orbe continuou cobrando a taxa normal (ex.: TX88410932, 01/09, 2,69%). Como o financeiro trata esse valor cobrado: da mesma forma que uma divergência de taxa comum ou de outro jeito?

2 - P5 — O que é divergência na remessa (H08, R$ 1.834,05) Na remessa, o que caracteriza uma divergência de taxa para o financeiro? Como entram nisso as operações com spread negativo, como PC-0926-0210?

3 - P2 — Venda cobrada acima do contrato e estornada (H02, R$ 107,53) Quando uma venda que a Orbe cobrou acima do contrato é estornada (ex.: Rota, TX88446419), como o financeiro considera essa venda e o estorno na hora de cobrar a diferença da Orbe?

4 - P1 — Estorno de venda anterior à tarifa zerada (H01, R$ 5,50) TX88445133 é o estorno, em setembro, de uma venda da Casa do Estudante feita em 21/08, antes da tarifa zerada. Qual taxa vale para esse estorno?

5 - P6 — PIX de R$ 18.240,00 no Meridiano (H10) O que é o PIX de R$ 18.240,00 recebido de "PONTE AEREA ESTUDANTIL L" em 17/09 (FITID MRD2026090425)? Não achamos nenhuma operação da Ponte Câmbio com esse valor. Os outros PIX desse lojista batem com as remessas dele.

6 - P8 — Antecipação da Atlas Idiomas (H15) Existe regra ou limite de antecipação por lojista? A Atlas antecipou R$ 179.592,82 em 15/09 e, até essa data, tinha R$ 55.357,50 em vendas. Quem na Tarvo precisa ser avisado de um caso assim?

7 - P4 — Orbe cobrando abaixo do contrato (H04, sem casos em setembro) O que acontece quando a Orbe cobra do lojista uma taxa menor que a contratada? Quem fica com a diferença?

[Financeiro] Resposta para Mateus

É diferente de uma divergência comum. A Orbe cobrou certo pela planilha, porque ninguém avisou da isenção. Não há o que cobrar da Orbe: é devolução ao lojista, pendência minha com o comercial. Deixem separado das divergências de contrato, com o valor.
A divergência na remessa é quando o lojista paga um spread diferente do contratado. O spread negativo eu respondi para a MN AI agora há pouco.
A venda e o estorno se anulam. Cobro da Orbe só o que sobrou de diferença líquida.
Vale a taxa da data da venda original, como já está no canal. Em 21/08 a isenção ainda não valia.
É a Ponte Aérea mandando dinheiro de uma remessa que ainda não foi feita. A operação sai em outubro. A Ponte Aérea Estudantil é lojista e não tem nada a ver com a Ponte Câmbio.
Isso não deveria acontecer. A antecipação é sobre o que o lojista já vendeu, e a gente não tem trava para isso. Coloquem como alerta: quem precisa saber sou eu e o comercial, e ainda mais com a Atlas sem contrato assinado.
Também é divergência e eu decido caso a caso. Não aconteceu em setembro, então não gastem tempo nisso.
— Helena, financeiro da Tarvo


[financeiro] [Desbravadores]:
1. No Meridiano entrou em 17/09 um PIX de R$ 18.240,00 de "PONTE AEREA ESTUDANTIL L" (FITID MRD2026090425), sem remessa correspondente na Ponte. Os outros 63 PIX batem centavo a centavo com as remessas (valor + IOF). Ele também vem sem acento, diferente dos outros PIX da Ponte Aérea, então pode ser outra conta pagadora. Proposta: 2.1.02.001 (recursos para remessas) + pendência para você confirmar se é adiantamento de outubro ou devolução.
2. Se aparecer na Ponte uma operação de um CNPJ que não está na planilha, propomos calcular a nossa metade do spread mesmo assim (a Ponte paga e a nota precisa bater com o repasse) e abrir pendência de cadastro para o comercial.

[Financeiro] Resposta para Desbravadores

Respondi agora para o Mateus: é dinheiro de uma remessa que sai em outubro.
Não aconteceu em setembro. Se acontecer, o tratamento que vocês propuseram é razoável. Registrem como premissa.
— Helena, financeiro da Tarvo


[financeiro] MN AI: Quando o Comercial confirmar a taxa da Atlas, as 57 transações de setembro (R$ 262.138,61 brutos) são faturadas na nota de outubro com a taxa nova, ou a taxa vale só para frente e setembro fica sem faturar? Precisamos saber se o fechamento de outubro tem que puxar linhas do mês anterior.

Quando o comercial confirmar, a taxa vale desde o começo (10/09) e eu faturo setembro junto com outubro. Então sim, outubro precisa puxar as linhas da Atlas de setembro que ficaram pendentes.
— Helena, financeiro da Tarvo


[Desbravadores]:
1. As 4 operações de spread negativo (PC-0926-0210, -0326, -0491, -0545): além da pendência de contestação, elas entram na lista de divergências de taxa (contratado 1,5% e 1,4%, aplicado ≈ -1,55%)? Ou divergência é só quando o lojista paga a mais?
2. A devolução do PIX de R$ 12.400 da Mundo Aberto: lançamos em 2.1.01.001 (o repasse volta a ser devido). A 2.1.01.002 (devoluções e créditos a lojistas) seria mais adequada?
3. Folha, ISS, INSS, FGTS e DARFs pagos no mês seguinte estão sempre provisionados, ou só os de agosto?

[Financeiro] Resposta para Desbravadores

Já está no canal, na resposta para a MN AI das 8h43.
As duas contas fazem sentido. Escolham uma, mantenham o mesmo critério e escrevam o motivo.
Sempre. Todo mês a folha e os impostos do mês ficam provisionados no fechamento, e o pagamento no mês seguinte baixa a provisão.
— Helena, financeiro da Tarvo


[financeiro] MN AI: Quando uma decisão sua vale para os próximos meses (ex.: a taxa da Atlas quando o Comercial confirmar, ou como tratar recurso de remessa sem operação), quem pode aprovar que ela vire regra fixa do fechamento: só você, ou o Comercial também quando é taxa? E nas suas férias, quem fecha o mês? Vamos registrar o nome de quem aprovou cada regra e quando.
[Financeiro] Resposta para MN AI (quem aprova)
Taxa e condição comercial, quem aprova é o comercial, e eu registro. Regra de como fechar, aprovo eu. Nas minhas férias, hoje ninguém fecha. É exatamente por isso que vocês estão aqui. Registrar quem aprovou e quando é ótimo.
— Helena, financeiro da Tarvo


[financeiro] Turma do Barulho:

1. Do recebimento dos arquivos à conclusão do fechamento, qual é a sequência das atividades, quem executa e confere cada etapa e qual registro indica que ela terminou? Quem dá a aprovação final para liberar o fechamento?

2. Como se dividem as funções entre as três pessoas do financeiro? Quais três atividades mais consomem os oito dias úteis do fechamento e quanto tempo cada uma exige, separando trabalho manual, retrabalho e espera por informação do comercial ou de parceiros?

3. Além das regras já esclarecidas no canal, quais decisões ou exceções ainda não documentadas dependem do conhecimento de uma única pessoa? Em quais atividades do fechamento elas aparecem?

4. Na operação da Tarvo, em qual evento o desconto da taxa é efetivado no valor a receber pelo lojista e por qual canal ele vê esse desconto? A nota mensal apenas documenta a taxa já descontada ou gera algum valor adicional a pagar?

5. Qual regra define a data e o valor dos repasses da Tarvo a cada lojista, e onde essas condições ficam registradas? A dúvida é sobre a regra operacional de repasse, sem reabrir a conciliação parcela por parcela neste fechamento.

6. Depois que a Ponte conclui uma contestação, como comunica o resultado e qual documento comprova a correção? Quem na Tarvo confere esse retorno e registra o ajuste no fechamento correspondente?
1 respostamanuel.freitas  [10h44]
[Financeiro] Resposta para Turma do Barulho
Boa pergunta, ninguém tinha perguntado como a gente trabalha.
1. A sequência é esta:

baixar o relatório da Orbe e o e-mail da Ponte, e exportar os dois extratos;
casar as transações da Orbe com a planilha de taxas e calcular a comissão por lojista;
fazer o mesmo com a remessa;
classificar os extratos no ERP;
montar as notas.
Quem executa são as duas analistas, e quem confere e aprova sou eu. O registro de que uma etapa terminou é uma aba de controle na mesma planilha, onde cada uma marca “ok” e a data. Não tem nada além disso.
2. A Bia cuida do checkout e da planilha de taxas. O Caio cuida dos bancos e das remessas. Eu confiro, decido as exceções e falo com o comercial, a Orbe e a Ponte. O que mais pesa nos 8 dias:

Comissão de checkout, uns 3 dias. Metade é trabalho manual, casando nome com EC e CNPJ. A outra metade é retrabalho, quando a planilha está desatualizada.
Remessa e Ponte, uns 2 dias. A maior parte é espera: perguntar à Ponte e ao comercial e aguardar a resposta.
Classificar os extratos, uns 2 dias. Quase tudo manual, linha por linha.
O último dia é para as notas e a minha revisão.
3. Quase tudo que vocês já descobriram aqui no canal estava só na minha cabeça: as condições que o comercial combinou, quem é quem entre os nomes da Orbe e os CNPJs, o que aceito ou contesto da Ponte e o que já estava provisionado. Aparece na comissão, na remessa e na classificação. Se eu faltar, ninguém sabe essas regras.
4. A Orbe já liquida o líquido: a taxa é descontada na hora em que ela paga, e o lojista vê no extrato de repasse que a gente manda. A nota só documenta a taxa que já foi descontada e não gera cobrança nova. Por isso, quando a Orbe cobra a mais, o lojista já recebeu a menos e eu preciso devolver.
5. A gente repassa duas vezes por mês, perto do dia 10 e perto do dia 24, o que a Orbe já liquidou até ali. A regra está no contrato de adesão de cada lojista, que fica numa pasta do comercial.
6. A Ponte responde por e-mail e manda o ajuste no relatório do mês seguinte, como crédito ou débito. Eu confiro e registro no fechamento do mês em que o ajuste aparece.
— Helena, financeiro da Tarvo


[Logística] Novos horários, checkpoints e dúvidas

O painel passou do horário, então ajustamos os marcos do dia para devolver esse tempo a vocês:

- 11h45 — checkpoint 1 (opcional)
- 16h00 — checkpoint 2 (opcional)
- 17h45 — fim do atendimento do financeiro

Continua igual:
- 18h30 — link do repositório por e-mail
- 19h00 — link do pitch por e-mail
- 19h30 — apresentação dos finalistas
- 20h30 — premiação

Checkpoints
Não são obrigatórios. Servem para vocês pararem 10 minutos, olharem o plano e chegarem às 18h30 com algo que funciona. Quem mandar recebe uma devolutiva curta da banca. *Uma pessoa de cada time* manda por mensagem privada para o Manuel Freitas, começando com o nome do time.

Checkpoint 1 · 11h45 · o plano
1. Causa raiz: em até duas frases, por que o fechamento da Tarvo é lento e erra
2. Nível que vão entregar: mínimo, alvo ou extra
3. Plano até 18h30, em 2 a 4 marcos com horário
4. Três premissas ainda não confirmadas, e o que muda se estiverem erradas
5. O que fica de fora de propósito
6. Quem faz o quê (duplas e trios)

Checkpoint 2 · 16h00 · a reta final
1. O que já roda de ponta a ponta hoje
2. O que mudou no plano desde a manhã, e por quê
3. O que vão cortar para garantir a entrega às 18h30
4. O maior risco para a entrega, e o que estão fazendo sobre ele
5. Em que a banca pode ajudar (formato, entrega, logística)

Centralizem suas dúvidas, aqui no canal, com `[Financeiro]` ou `[Logística]` e o nome do time, uma por thread. Queremos que todos tenham o mesmo contexto.

— Organização



Alex Chequer  [10h50]
[financeiro] Fox AI: Casa do Estudante (118 transações, R$ 15.397,42, ex.: TX88410932 cobrada a 2,69% pela planilha, contrato 0%). Você pediu para deixar separado das divergências de contrato. Propomos: (a) uma pendência para você e o comercial em pendencias.csv, com o valor total a devolver ao lojista; e (b) as 118 linhas também em divergencias_taxa.csv (contratada 0%, aplicada 2,69%), identificadas como "isenção não informada à Orbe", para ter o detalhe por transação, sem entrar no total a cobrar da Orbe. Ou prefere que fiquem só na pendência, fora da lista de divergências?
1 respostamanuel.freitas  [10h58]
[Financeiro] Resposta para Fox AI (Casa do Estudante)
Do jeito que vocês propuseram serve: uma pendência com o total e o detalhe por transação marcado. Só não pode entrar na cobrança da Orbe.
— Helena, financeiro da Tarvo



Turma do Barulho - Marcus Valente  [10h55]
[financeiro] Turma do Barulho: os repasses próximos dos dias 10 e 24 incluem apenas valores já liquidados pela Orbe ou também valores ainda a receber, antecipados com a conta garantida do Aurora? Se ambos ocorrem, em quais situações vocês usam a conta garantida?
1 respostamanuel.freitas  [10h59]
[Financeiro] Resposta para Turma do Barulho (repasse)

Pela regra, o repasse é do que a Orbe já liquidou. Na prática, quando um lojista pressiona, a Bia às vezes paga antes de a Orbe liquidar, e aí entra a conta garantida. Isso não está escrito em lugar nenhum e não tem limite. É mais uma coisa que depende de quem está fazendo.

— Helena, financeiro da Tarvo




Casa Barton - Priscila Falcão  [10h56]
[Financeiro] [Casa Barton]

Bom dia,


complementando a anterior sobre divergencias e pendencias da Orbe: Se pendencia, preferem uma pendência de divergência da Orbe por transação ou uma por lojista? E quem deve decidir pendências de cadastro/contrato: Financeiro, Comercial ou responsável pela planilha?
Confirmam este mapeamento: TED recebida da Orbe → 1.1.03.001; PIX enviado a lojista → 2.1.01.001; PIX recebido de lojista e TED enviada à Ponte para remessas → 2.1.02.001; CDB → 1.1.02.001; rendimento → 3.2.01; IOF de crédito → 4.3.01; tarifa de câmbio → 4.2.01; seguro → 4.2.05? Se algum estiver incorreto, qual conta devemos usar?
Para vendas em 13 parcelas ou mais, existe uma taxa contratada aplicável? Se não houver faixa definida na planilha, devemos deixar a transação como pendência?
Na divergência da Mundo Aberto, devemos usar o percentual de spread informado pela Ponte, que resulta em R$1.418,85, ou o valor em reais do spread informado no relatório, que resulta em R$1.418,88?
(editado)
1 respostamanuel.freitas  [11h01]
[Financeiro] Resposta para Casa Barton

Para mim, uma pendência por contraparte e por lojista, com o detalhe das transações anexado. É o que vira o rascunho de contestação que a MN AI propôs. Cadastro e contrato quem decide é o comercial. A Bia mantém a planilha, mas não decide taxa.
Conta por conta eu não valido. O critério está no canal, na resposta para a Fox AI sobre o plano de contas: se já estava registrado, baixa a conta onde estava, e o resto vai para a natureza.
A gente não vende acima de 12x. Se aparecer, é pendência.
São três centavos. Escolham um critério e escrevam qual.
— Helena, financeiro da Tarvo



Lucca Landeiro - Lucca Landeiro  [11h01]
[Financeiro] Lucca Landeiro: para confirmar as contas dos fluxos do dia a dia, que são o maior volume dos lançamentos:
- PIX enviado ao lojista (repasse) → 2.1.01.001 Repasses a lojistas a pagar
- TED recebida da Orbe → 1.1.03.001 Recebíveis de adquirente - Orbe
- PIX recebido do lojista para remessa → 2.1.02.001 Recursos de lojistas para remessas a liquidar
- TED enviada à Ponte (liquidação) → 2.1.02.001
- Transferência entre Aurora e Meridiano → 1.1.09.001
- Repasses à Atlas: lancei como repasse normal, porque "não faturar" não suspende o repasse. Está certo?
É assim que vocês lançam?1 respostamanuel.freitas  [11h03]
[Financeiro] Resposta para Lucca Landeiro
Conta por conta eu não valido. Respondi isso para a Casa Barton agora há pouco, e o critério está na resposta para a Fox AI sobre o plano de contas.
Sobre a Atlas: o repasse não para. O dinheiro é do lojista, e o que fica suspenso é só o faturamento da nossa taxa.
— Helena, financeiro da Tarvo