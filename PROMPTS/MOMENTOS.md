# Momentos que importaram

## 1. A IA disse que a aritmética da Orbe "fechava", e não fechava (erro da IA)

**O que pedi:** um diagnóstico de cada arquivo do data pack: estrutura, armadilhas de formato e chaves de ligação.

**O que a IA devolveu:** na leitura do relatório da Orbe, a IA afirmou que a aritmética interna fechava em todas as 1.943 linhas (bruto × taxa = valor_taxa). A conferência tinha usado tolerância de R$ 0,011, e essa folga escondia exatamente a diferença de um centavo.

**O que fiz com isso:** observei que o `valor_taxa` parecia truncado e pedi que a IA verificasse. Na recontagem em decimal exato, a truncagem bateu em 1.943 de 1.943 linhas, contra 942 do arredondamento. A diferença aparece em 1.001 linhas (ex.: TX88410932, 608,88 × 2,69% = 16,378872 → arquivo 16,37). Isso muda o cálculo: comparar a taxa contratada arredondada com o valor truncado da Orbe geraria cerca de 1.000 divergências falsas de R$ 0,01, e alarme falso conta contra. Daqui em diante, toda conferência numérica é feita sem tolerância, em decimal exato.

## 2. Uma premissa do PRD, tirada do canal, não se sustentava nos dados (premissa errada que a IA tinha incorporado)

**O que pedi:** implementar o B6 (classificação dos extratos), começando por reler as fontes (PRD, HIPOTESES, instruções, perguntas do Slack).

**O que a IA devolveu:** o PRD 7.7, escrito com a IA, previa detectar o PIX de R$ 18.240 sem operação conciliando os PIX recebidos no Meridiano com Σ(Valor R$ + IOF) das remessas de cada lojista. A premissa vinha de afirmações de outros times no canal ("os outros 63 PIX batem centavo a centavo com as remessas") e tinha entrado no `HIPOTESES.md` (I8) como fato. Antes de codar, a IA testou a premissa nos dados: as TEDs de liquidação à Ponte batem com as operações do dia (21 de 21), mas os PIX dos lojistas não batem nem por dia nem por janela até o próximo PIX. Exemplo: a Rota mandou R$ 668 mil em PIX contra R$ 141 mil de operações no mês.

**O que fiz com isso:** tiramos a conciliação de PIX do motor e mantivemos só a da TED da Ponte. O R$ 18.240 passou a ser tratado pela resposta da Helena (adiantamento de uma remessa que sai em outubro), num alerta configurado só para setembro. Corrigimos o PRD 7.7 e o I8 do `HIPOTESES.md`. Lição: afirmação de outro time no canal não é fato dos dados. Entra como premissa até ser conferida no arquivo.
