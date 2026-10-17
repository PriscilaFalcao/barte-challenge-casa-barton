# Momentos que importaram

## 1. A IA disse que a aritmética da Orbe "fechava", e não fechava (erro da IA)

**O que pedi:** um diagnóstico de cada arquivo do data pack: estrutura, armadilhas de formato e chaves de ligação.

**O que a IA devolveu:** na leitura do relatório da Orbe, a IA afirmou que a aritmética interna fechava em todas as 1.943 linhas (bruto × taxa = valor_taxa). A conferência tinha usado tolerância de R$ 0,011, e essa folga escondia exatamente a diferença de um centavo.

**O que fiz com isso:** observei que o `valor_taxa` parecia truncado e pedi que a IA verificasse. Na recontagem em decimal exato, a truncagem bateu em 1.943 de 1.943 linhas, contra 942 do arredondamento. A diferença aparece em 1.001 linhas (ex.: TX88410932, 608,88 × 2,69% = 16,378872 → arquivo 16,37). Isso muda o cálculo: comparar a taxa contratada arredondada com o valor truncado da Orbe geraria cerca de 1.000 divergências falsas de R$ 0,01, e alarme falso conta contra. Daqui em diante, toda conferência numérica é feita sem tolerância, em decimal exato.

## 2. Uma premissa do PRD, tirada do canal, não se sustentava nos dados (premissa errada que a IA tinha incorporado)

**O que pedi:** implementar o B6 (classificação dos extratos), começando por reler as fontes (PRD, HIPOTESES, instruções, perguntas do Slack).

**O que a IA devolveu:** o PRD 7.7, escrito com a IA, previa detectar o PIX de R$ 18.240 sem operação conciliando os PIX recebidos no Meridiano com Σ(Valor R$ + IOF) das remessas de cada lojista. A premissa vinha de afirmações de outros times no canal ("os outros 63 PIX batem centavo a centavo com as remessas") e tinha entrado no `HIPOTESES.md` (I8) como fato. Antes de codar, a IA testou a premissa nos dados: as TEDs de liquidação à Ponte batem com as operações do dia (21 de 21), mas os PIX de cada lojista não batem com as operações dele, nem por dia nem por janela até o próximo PIX. Exemplo: a Rota mandou R$ 668 mil em PIX contra R$ 141 mil de operações próprias. A afirmação só vale no total do mês: Σ PIX − Σ TEDs à Ponte dá exatamente R$ 18.240,00. Isso confirma o valor, mas não aponta qual PIX está sobrando.

**O que fiz com isso:** tiramos a conciliação de PIX do motor e mantivemos só a da TED da Ponte. O R$ 18.240 passou a ser tratado pela resposta da Helena (adiantamento de uma remessa que sai em outubro), num alerta configurado só para setembro. Corrigimos o PRD 7.7 e o I8 do `HIPOTESES.md`. Lição: afirmação de outro time no canal não é fato dos dados. Entra como premissa até ser conferida no arquivo.

## 3. A IA disse que recuperar o mês pendente da Atlas "exigiria guardar histórico", e o histórico já existia (erro da IA)

**O que pedi:** corrigir tudo o que ainda faltava depois de uma auditoria das regras da Helena. Uma delas: quando o comercial confirmar a taxa da Atlas, outubro tem que faturar as linhas de setembro (Helena, 11h41).

**O que a IA devolveu:** deixou isso como limitação e criou só uma chave de configuração manual, explicando que automatizar exigiria "guardar o histórico dos fechamentos", como se ele não existisse.

**O que fiz com isso:** questionei: "já não estamos fazendo isso? Tem uma aba de histórico só pra isso". A IA conferiu no código e reconheceu a imprecisão: a interface já guardava arquivos, saídas e decisões de cada mês, mas nenhuma etapa do cálculo lia um mês anterior (e cada fechamento tem o seu próprio banco de estado). Pedi para implementar. Agora o fechamento lê as pendências `SEM_CONTRATO` dos meses anteriores e o relatório da Orbe guardado em cada um, recupera as linhas quando a EC já tem contrato e marca o rastro com `+RECUP` para não faturar duas vezes. Validei com um "outubro" sintético: as 57 linhas de setembro entraram na comissão e na nota, a soma do rastro fechou e um fechamento seguinte não puxou as mesmas linhas de novo.

## 4. Os testes estavam verdes com um valor errado: a auditoria contra a fonte achou o desvio

**O que pedi:** verificar se todas as instruções do desafio e as regras de negócio (só as assinadas pela Helena) estavam sendo seguidas.

**O que a IA devolveu:** em vez de confiar nos 390 testes, recalculou checkout e remessa direto dos arquivos de dados, sem usar o código do projeto. Os números batiam (comissões, 210 divergências, R$ 39.543,45 de remessa), mas apareceram dois desvios: a devolução à Casa do Estudante estava em R$ 15.397,42 (a fórmula da divergência), quando a Helena pediu duas vezes o valor descontado de fato, R$ 15.396,77; e as pendências de spread negativo traziam só um dos dois valores que ela pediu (o do relatório e a diferença até o contrato). Também achou links quebrados no README.

**O que fiz com isso:** mandei corrigir. Um teste de integração tinha o valor errado como esperado, por isso estava verde: atualizei o teste junto com o código. A lição que ficou: teste verde só prova que o código faz o que o teste diz; a regra de negócio se confere contra a fonte (aqui, as respostas assinadas pela Helena e os arquivos originais).
