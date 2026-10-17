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

A interface aceita as fontes originais do fechamento, com um ou mais arquivos de cada uma (no campo da Orbe entram juntos o relatório `01_` e os ajustes tardios `06_`, no mesmo formato): Orbe (`.csv`), taxas contratadas (`.xlsx`), Ponte Câmbio (`.eml`), plano de contas (`.csv`), extrato Aurora (`.csv`) e extrato Meridiano (`.ofx`). É possível enviar os arquivos individualmente ou em lote; os CSVs do lote são identificados pelo cabeçalho. A pré-validação executa o pipeline sem IA; o fechamento usa estado B8 isolado por fechamento, acompanha etapas em tempo real e atualiza fila, decisões e checkpoints. A fila aceita observações, classificação de conta por caso ou regra e vínculo de EC a lojista. O gate final impede o fechamento enquanto houver pendências bloqueantes e registra quem fechou, a justificativa e hashes SHA-256 das saídas.

Para habilitar os agentes, copie `.env.example` para `.env` na raiz do repositório e configure a credencial localmente. Sem credencial, o fluxo funciona em modo sem IA e mantém exceções na fila humana. Não é necessário criar `.env` para iniciar a interface.

A navegação destaca em rosa a seção selecionada. Use **Novo fechamento** para iniciar o fluxo. Durante a conferência e a execução, um indicador visual informa que o processamento está em andamento; a criação de outro fechamento e o envio de arquivos ficam bloqueados até a conclusão. Nas saídas, o botão **Baixar todas as saídas** usa um ícone de download para identificar o arquivo ZIP.

## Executar pelo terminal

```powershell
python -m tarvo fechar --mes 2026-09 --dados dados --saida saida
```

Cada fonte pode ter mais de um arquivo em `dados/`, achados pelo prefixo (`01_`/`06_` Orbe, `02_`, `03_`, `04_`, `05a_`, `05b_`) e somados. O `06_*.csv` (ajustes tardios da Orbe, mesmo formato do 01) é lido junto com o 01. Mesmo `id_transacao` em dois arquivos: a linha mais recente permanece, a mais antiga sai, e a troca vira pendência (ver `docs/HIPOTESES.md`, seção 5).