# Casa Barton | Fechamento financeiro

Solução do time **Casa Barton** para o case Tarvo Pagamentos do Desafio Barte AI. Consome os arquivos originais dos parceiros e bancos, calcula o fechamento mensal e apresenta as exceções que precisam de uma pessoa.

A interface usa a marca Casa Barton; o pacote Python e os comandos continuam com o nome técnico `tarvo`.

## O que a solução entrega

- Comissões por lojista, separadas em checkout e remessa.
- Divergências entre taxas contratadas e aplicadas, com impacto em reais.
- Relação de notas fiscais a emitir.
- Lançamentos dos bancos Aurora e Meridiano classificados no plano de contas.
- Pendências com motivo, responsável e propostas dos agentes, quando disponíveis.
- Rastro dos valores até as linhas dos arquivos de origem.
- Interface para upload, acompanhamento da execução, decisões humanas e download das saídas.

O problema não é apenas somar arquivos: há cadastros incompletos, contratos ambíguos, duplicatas e regras que estavam dispersas entre financeiro e comercial. As causas, evidências e premissas estão em [Hipóteses](docs/HIPOTESES.md); as perguntas e respostas estão em [Registro do financeiro](docs/perguntas_slack.md).

## 1. Requisitos

- **Python 3.11 ou superior** e `pip`. O ambiente usado no desenvolvimento tem Python 3.12.
- Git para clonar o repositório.
- Navegador atualizado para usar a interface.
- Acesso à internet para instalar dependências e, opcionalmente, chamar a API da Anthropic.

Não é necessário instalar Node.js, banco de dados externo ou ferramentas de build do front. A interface usa HTML, CSS e JavaScript; o estado local usa SQLite.

Os exemplos abaixo usam **PowerShell no Windows**, executados na raiz do repositório.

## 2. Instalar do zero

```powershell
git clone https://github.com/PriscilaFalcao/barte-challenge-casa-barton.git
Set-Location .\barte-challenge-casa-barton
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Os comandos usam diretamente o Python do ambiente virtual, sem precisar ativá-lo ou alterar a política de execução do PowerShell. Se `python` não estiver disponível, use `py -3` para criar o ambiente virtual.

Dependências: `openpyxl` para planilhas, `PyYAML` para configuração, SDK `anthropic` para os agentes e `pytest` para testes.

## 3. Configurar a IA — opcional

**Nenhuma chave é necessária para iniciar a interface ou calcular o fechamento.** Sem credencial, as exceções continuam na fila humana; o cálculo financeiro não depende de um LLM.

Para habilitar chamadas reais dos agentes:

```powershell
Copy-Item .env.example .env
```

Se já existir um arquivo `.env`, edite-o em vez de sobrescrevê-lo. Preencha localmente:

```dotenv
ANTHROPIC_API_KEY=sua_chave_aqui
```

O programa lê o arquivo `.env` da raiz; variáveis já definidas no ambiente têm precedência. Nunca publique a chave nem o arquivo `.env`, que está ignorado pelo Git.

Os modelos são definidos em [src/config/defaults.yaml](src/config/defaults.yaml): `claude-haiku-4-5` para o Classificador e `claude-sonnet-5-5` para o Intérprete de taxas e o Investigador. A credencial precisa ter acesso aos modelos configurados. As chamadas podem gerar cobrança; o limite padrão é de 60 chamadas novas por execução.

### Rodar sem chamadas externas

Para uma avaliação reproduzível sem consumir API, mesmo que haja uma chave configurada:

```powershell
$env:TARVO_SEM_IA = "1"
```

Para permitir chamadas novamente:

```powershell
Remove-Item Env:TARVO_SEM_IA -ErrorAction SilentlyContinue
```

O cache das respostas dos agentes (`cache/agentes/`) não vai para o repositório: é criado na primeira execução com IA, na máquina de quem roda, e reaproveitado nas execuções seguintes, inclusive no modo sem IA. Para uma execução sem respostas anteriores, use uma pasta de cache nova:

```powershell
$env:TARVO_CACHE_AGENTES = ".\data\cache-avaliacao"
```

Os agentes enviam contexto das exceções ao provedor quando habilitados. O cache pode conter entradas e respostas: trate-o como dado operacional, não como material para publicação indiscriminada.

## 4. Executar pela interface

```powershell
.\.venv\Scripts\python.exe -m tarvo web
```

Abra **[http://127.0.0.1:8000](http://127.0.0.1:8000)**. Mantenha o terminal aberto; use `Ctrl+C` para encerrar.

Para escolher outra porta:

```powershell
.\.venv\Scripts\python.exe -m tarvo web --port 8766
```

Nesse caso, acesse [http://127.0.0.1:8766](http://127.0.0.1:8766).

### Passo a passo do fechamento

1. Clique em **Novo fechamento** e escolha a competência. Para os dados fornecidos, use **setembro de 2026** (`2026-09`).
2. Envie os arquivos da pasta [dados](dados), individualmente ou em lote, incluindo os ajustes tardios da Orbe, quando houver.
3. Confira se cada arquivo foi encaminhado para a categoria correta. Arquivos não identificados aparecem em vermelho e não são enviados.
4. Clique em **Conferir arquivos**. A pré-validação lê os arquivos e executa o pipeline sem IA.
5. Clique em **Executar fechamento**. Acompanhe etapas, checkpoints e atividade dos agentes. Durante uma chamada, aparece uma animação com o nome do agente e o identificador do item analisado.
6. Consulte as tabelas e abra uma linha para ver o rastro de origem.
7. Na seção **Validações**, registre as decisões com autor e motivo. As decisões suportadas podem disparar uma reexecução.
8. Baixe as saídas individualmente ou em ZIP (o botão **Baixar todas as saídas** é o primeiro da faixa de downloads). O fechamento final só é permitido quando não há pendências bloqueantes; ficam registrados autor, justificativa e hashes SHA-256 das saídas.

### Como os uploads são identificados

Não é necessário manter o nome exato do arquivo do case. O front usa **regex no nome e extensão**, sem distinguir maiúsculas ou acentos:

| Categoria | Palavras reconhecidas no nome | Extensão |
|---|---|---|
| Comissões e ajustes Orbe | `orbe`, `comissão`, `comissões` | `.csv` |
| Taxas contratadas | `taxa`, `taxas` | `.xlsx` |
| Relatório Ponte | `ponte`, `câmbio`, `remessa`, `remessas` | `.eml` |
| Plano de contas | `plano de contas`, `plano contas`, `fênix` | `.csv` |
| Extrato Aurora | `aurora` | `.csv` |
| Extrato Meridiano | `meridiano` | `.ofx` |

Use espaços, hífens ou sublinhados entre palavras, por exemplo `extrato_aurora_outubro.csv`. Um nome genérico como `arquivo.csv` não é identificado; um nome que corresponda a mais de uma categoria é ambíguo. Renomeie esses arquivos sem alterar seu conteúdo e envie novamente. Os reconhecidos do mesmo lote continuam normalmente.

Cada categoria aceita um ou mais arquivos. O upload tem limite de **25 MiB por arquivo**. A identificação pelo nome não substitui a validação do conteúdo. O programa extrai o anexo da Ponte diretamente do `.eml`; não é necessário abrir o e-mail ou limpar os arquivos manualmente.

## 5. Executar pelo terminal

Para gerar as saídas do data pack sem chamadas externas:

```powershell
$env:TARVO_SEM_IA = "1"
.\.venv\Scripts\python.exe -m tarvo fechar --mes 2026-09 --dados .\dados --saida .\saida
```

Esse comando usa estado persistente em `data`: fila, decisões, regras e checkpoints. Ele escreve na pasta de saída indicada; para preservar uma execução anterior, escolha outra pasta.

Para executar sem persistir estado, fila ou checkpoints:

```powershell
.\.venv\Scripts\python.exe -m tarvo fechar --mes 2026-09 --dados .\dados --saida .\saida-avaliacao --sem-estado
```

`--sem-estado` não desabilita a IA por si só; use também `TARVO_SEM_IA=1` se não quiser chamadas externas.

### Arquivos de entrada no terminal

Ao contrário do upload web, a linha de comando procura arquivos por **prefixos**, preservando os nomes do data pack:

| Fonte | Padrão |
|---|---|
| Orbe | `01_*.csv` e, opcionalmente, `06_*.csv` |
| Taxas | `02_*.xlsx` |
| Ponte | `03_*.eml` |
| Plano de contas | `04_*.csv` |
| Aurora | `05a_*.csv` |
| Meridiano | `05b_*.ofx` |

O arquivo `06_` é opcional e lido junto com o relatório da Orbe. Se um `id_transacao` for substituído entre arquivos, a regra de seleção e a pendência gerada estão documentadas na seção 5 de [Hipóteses](docs/HIPOTESES.md).

Para outro mês, forneça arquivos do mesmo formato e mude `--mes`, `--dados` e `--saida`. Não basta trocar a competência mantendo os dados de setembro: se nem Orbe nem Ponte tiverem linhas do mês solicitado, a execução falha.

### Fila, decisões e regras

```powershell
.\.venv\Scripts\python.exe -m tarvo fila --mes 2026-09
.\.venv\Scripts\python.exe -m tarvo fila --mes 2026-09 --todas
.\.venv\Scripts\python.exe -m tarvo regras
```

Exemplo de observação humana sobre uma pendência:

```powershell
.\.venv\Scripts\python.exe -m tarvo decidir --mes 2026-09 --id PEN-DIVERGENCIA_ORBE-22224579000109-202609 --por "Analista" --motivo "Divergência conferida com a adquirente" --nota "Cobrar a diferença na próxima conciliação"
```

Use um identificador que exista na fila da sua execução. Depois, rode `fechar` novamente para aplicar a decisão. Uma observação não altera valores financeiros.

Também existem decisões de conta contábil e vínculo EC–CNPJ, além de promoção e desativação de regras. Consulte as opções antes de usá-las:

```powershell
.\.venv\Scripts\python.exe -m tarvo decidir --help
.\.venv\Scripts\python.exe -m tarvo regras --help
```

O parâmetro `--estado` permite escolher outra pasta nos comandos do terminal. Para operar sobre um fechamento criado pela interface, é necessário apontar para o estado daquele fechamento, e não para o estado padrão do terminal.

### Histórico de fechamentos

A aba **Histórico** do menu lateral lista todos os fechamentos já executados, do mês mais recente ao mais antigo. Cada cartão mostra a competência, a data da execução, se o mês está **Fechado** (com autor e justificativa) ou **Em aberto**, e os arquivos de saída daquele fechamento, cada um com link de download e tamanho, além de **Baixar todos** (ZIP). **Abrir fechamento** carrega aquele mês de volta na tela principal, com tabelas, rastro e fila.

- Só aparecem fechamentos que já têm saídas (execução concluída ou competência fechada). Fechamentos ainda em envio de arquivos ou em pré-validação não entram.
- Se um mês foi executado mais de uma vez em fechamentos diferentes, cada um aparece como um cartão próprio.
- A lista vem de `GET /api/closures`, que lê `data\web\fechamentos\<id>\state.json` e a pasta `saida`; nada é copiado ou duplicado. Os downloads usam o mesmo endpoint das saídas do fechamento atual.
- **Excluir** remove o fechamento por completo (arquivos enviados, saídas, decisões e registro de fechamento, em `data\web\fechamentos\<id>`), via `DELETE /api/closures/<id>`. Um popup de confirmação avisa que a ação não pode ser desfeita. Fechamento em execução não pode ser excluído (retorna 409). Se o fechamento excluído estava aberto na tela principal, ela volta ao estado inicial.
- Disponível apenas na interface; a execução pelo terminal não cria histórico.

## 6. Saídas e rastreabilidade

As saídas do data pack estão em [saida](saida). Uma nova execução pelo terminal usa `--saida`; pela interface, os arquivos ficam isolados em `data\web\fechamentos\<id>\saida` e podem ser baixados pela tela.

| Arquivo | Colunas obrigatórias |
|---|---|
| [comissoes_por_lojista.csv](saida/comissoes_por_lojista.csv) | `id_saida;cnpj;lojista;linha_negocio;comissao_brl` |
| [divergencias_taxa.csv](saida/divergencias_taxa.csv) | `id_saida;cnpj;linha_negocio;ref_origem;taxa_contratada_pct;taxa_aplicada_pct;diferenca_brl` |
| [notas_a_emitir.csv](saida/notas_a_emitir.csv) | `id_saida;tomador_cnpj;tomador;linha_negocio;valor_brl;discriminacao` |
| [lancamentos_classificados.csv](saida/lancamentos_classificados.csv) | `id_saida;banco;ref_origem;data;descricao;valor;conta_codigo;metodo;confianca` |
| [pendencias.csv](saida/pendencias.csv) | `id_saida;tipo;ref_origem;valor_brl;motivo;quem_decide` |
| [rastro.csv](saida/rastro.csv) | `id_saida;arquivo_origem;ref_origem;valor` |

Formato: UTF-8, separador `;`, ponto decimal, datas `AAAA-MM-DD` e CNPJ com 14 dígitos. Há colunas extras de auditoria. `linha_negocio` usa `CHECKOUT` ou `REMESSA`; `banco`, `AURORA` ou `MERIDIANO`; `metodo`, `REGRA`, `IA` ou `HUMANO`; a confiança vai de 0 a 1.

Pela interface há ainda o `decisoes.csv` (separador `;`, UTF-8), que registra o histórico da fila de validações: `id;id_saida;tipo_decisao;escopo;ativa;decidido_por;motivo;decidido_em;payload`. Entram as decisões ativas e as substituídas (`ativa` = `S` ou `N`), e o `payload` é o conteúdo da decisão em JSON. O arquivo é regenerado a cada download até o fechamento da competência; ao fechar, é gravado e seu hash SHA-256 entra no registro de fechamento. Fechamentos fechados antes dessa mudança recebem o arquivo no primeiro download, sem hash no registro. Ele não existe na execução pelo terminal, que não tem fila de decisões.

O `rastro.csv` liga o `id_saida` ao arquivo e à referência de origem: `id_transacao` na Orbe, número da operação na Ponte, linha física `L...` no Aurora e FITID no Meridiano. Os validadores conferem a reconciliação dos valores em decimal exato. Consulte também o [resumo](saida/resumo.md) e o [log da execução](saida/execucao.log), que registra contagens e descartes.

## 7. Onde a IA atua — e onde não atua

O mesmo pipeline Python atende o terminal e a interface:

```text
Arquivos → ingestão → checkout → divergências → remessas → notas
         → bancos → agentes nas exceções → validação e escrita
```

**Cálculos financeiros são determinísticos**, com `Decimal` e regras explícitas. Os agentes não calculam dinheiro nem escolhem taxas:

| Agente | Papel |
|---|---|
| Classificador | Sugere conta entre candidatas válidas para lançamentos sem classificação confiável; a aplicação depende do guardrail e do limiar configurado. |
| Intérprete de taxas | Propõe interpretação de contratos ambíguos, sem aplicar taxa automaticamente. |
| Investigador | Acrescenta hipóteses e perguntas para a pessoa responsável, sem alterar os valores. |

O orquestrador é código, não um LLM. Respostas são validadas e cacheadas por hash. Erro de API, resposta inválida ou limite de chamadas mantém a exceção no fluxo humano. No data pack original, nem todos os agentes precisam ser chamados: ter regras suficientes não é falha da IA.

## 8. Testes

Após a instalação com `.[dev]`, execute a suíte Python:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Para verificar apenas agentes, estado e integração web:

```powershell
.\.venv\Scripts\python.exe -m pytest .\src\tests\test_agentes.py .\src\tests\test_b8.py .\src\tests\test_web.py -q
```

Os testes de agentes usam clientes falsos, sem precisar de chave ou API. Se tiver Node.js instalado, os testes específicos de identificação de uploads podem ser executados separadamente:

```powershell
node .\src\tests\test_upload_identification.cjs
```

## 9. Limitações conhecidas

- **Uso local:** o servidor escuta apenas em `127.0.0.1`. Não há autenticação de usuários ou implantação multiusuário pronta para produção; não exponha o serviço diretamente na internet.
- **Formatos conhecidos:** não há parser genérico para qualquer relatório bancário ou planilha. Mudanças de layout exigem adaptação; nomes não reconhecidos no upload precisam ser renomeados.
- **Configurações na interface:** a tela de configurações gerais ainda não está integrada. Os defaults ficam em [config](config); a fila permite apenas os tipos de decisão implementados. Corrigir uma taxa ambígua pode exigir corrigir a fonte/configuração, não apenas aprovar a proposta do agente.
- **Orbe × banco:** não há conciliação parcela a parcela sem a agenda de recebíveis.
- **Histórico de contratos:** estornos de vendas de agosto dependem do histórico disponível na planilha atual.
- **Atlas:** sem contrato confirmado, não há comissão, nota ou divergência calculada para ela. Recuperar automaticamente em outubro os valores de setembro após confirmar a taxa ainda não está implementado.
- **Classificação bancária:** regras genéricas de PIX não comprovam a identidade do beneficiário. Um novo fornecedor pode exigir revisão da regra.
- **Meridiano:** sem saldo inicial no OFX, não é possível validar toda a cadeia de saldos.
- **Alertas específicos do case:** alguns alertas configurados para setembro não são detectores genéricos para outubro.
- **Decisões externas:** o sistema gera a relação de notas, propostas e pendências; não emite nota fiscal, efetua devolução ou envia contestação automaticamente.
- **Checkpoints e cache:** alterações de código invalidam checkpoints. Chamadas em cache podem aparecer mesmo sem credencial; para uma avaliação isolada, use pastas novas de estado, saída e cache.

Os detalhes e o impacto das premissas estão em [Hipóteses, seção 6](docs/HIPOTESES.md#6-limitações-conhecidas).

### Problemas comuns

| Sintoma | Como proceder |
|---|---|
| `No module named tarvo` | Use o Python de `.venv` e repita a instalação `-m pip install -e ".[dev]"` na raiz. |
| Porta ocupada | Inicie com `web --port 8766` ou outra porta livre e abra o endereço correspondente. |
| Arquivo em vermelho no upload | Inclua uma palavra reconhecida no nome e mantenha a extensão correta; não altere o conteúdo. |
| Nenhum dado para a competência | Confira mês e arquivos. O pacote fornecido é de setembro/2026. |
| Sem chamadas de IA | Confira credencial, acesso aos modelos, `TARVO_SEM_IA`, cache e se realmente existem exceções roteadas. |
| Fechamento final bloqueado | Consulte os itens bloqueantes em **Validações** e registre a decisão adequada. |

## 10. Documentação e evidências do desafio

- [Instruções dos participantes](docs/01_instrucoes_participantes.docx): requisitos originais de entrega e avaliação.
- [Hipóteses e premissas](docs/HIPOTESES.md): causas, regras confirmadas, decisões assumidas e limitações.
- [Perguntas e respostas do financeiro](docs/perguntas_slack.md): evidências de descoberta das regras.
- [PRD](docs/PRD.md) e [checkpoints](docs/CHECKPOINTS.md): planejamento e evolução do escopo; partes descrevem objetivos, não necessariamente funcionalidades já disponíveis.
- [Histórico de sessões de IA](PROMPTS) e [momentos importantes](PROMPTS/MOMENTOS.md): registros de uso, verificação e correção da IA.
- [Data pack](dados/00_LEIA-ME.md): descrição das fontes sintéticas; empresas, pessoas e identificadores são fictícios.

**Atenção ao empacotamento da entrega:** o documento do desafio pede `HIPOTESES.md` na raiz. Neste repositório, o documento está em `docs/HIPOTESES.md`; o link acima permite encontrá-lo, mas não substitui essa exigência de localização. Antes do envio final, ajuste essa organização, confira os seis CSVs em `saida/` e a completude dos históricos em `PROMPTS/`. Não inclua credenciais ou dados pessoais nos materiais publicados.
