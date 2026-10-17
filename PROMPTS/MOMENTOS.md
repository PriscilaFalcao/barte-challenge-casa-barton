# Momentos que importaram

## 1. A IA disse que a aritmética da Orbe "fechava", e não fechava (erro da IA)

**O que pedi:** um diagnóstico de cada arquivo do data pack: estrutura, armadilhas de formato e chaves de ligação.

**O que a IA devolveu:** na leitura do relatório da Orbe, a IA afirmou que a aritmética interna fechava em todas as 1.943 linhas (bruto × taxa = valor_taxa). A conferência tinha usado tolerância de R$ 0,011, e essa folga escondia exatamente a diferença de um centavo.

**O que fiz com isso:** observei que o `valor_taxa` parecia truncado e pedi que a IA verificasse. Na recontagem em decimal exato, a truncagem bateu em 1.943 de 1.943 linhas, contra 942 do arredondamento. A diferença aparece em 1.001 linhas (ex.: TX88410932, 608,88 × 2,69% = 16,378872 → arquivo 16,37). Isso muda o cálculo: comparar a taxa contratada arredondada com o valor truncado da Orbe geraria cerca de 1.000 divergências falsas de R$ 0,01, e alarme falso conta contra. Daqui em diante, toda conferência numérica é feita sem tolerância, em decimal exato.
