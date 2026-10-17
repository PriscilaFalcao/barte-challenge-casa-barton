"""Fechamento do mês: checkout, remessa, divergências e notas. Classificação dos extratos entra no B6."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import carregar_defaults
from .contracts.resolver import Resolvedor
from .core.competencia import no_mes
from .core.ledger import Ledger
from .core.rastro import Rastro
from .engines.checkout import calcular_checkout
from .engines.divergencias import calcular_divergencias
from .engines.notas import calcular_notas
from .engines.remessa import calcular_remessa
from .identity.registro import Registro
from .ingest.erros import LayoutError
from .ingest.orbe import ARQUIVO as ARQUIVO_ORBE
from .ingest.orbe import ler_orbe
from .ingest.ponte import ARQUIVO as ARQUIVO_PONTE
from .ingest.ponte import ler_ponte
from .ingest.taxas import ARQUIVO as ARQUIVO_TAXAS
from .ingest.taxas import ler_taxas
from .output.validators import validar_i_d1, validar_i_n1, validar_i_r1, validar_i_r3
from .output.writers import escrever_csv, escrever_rastro


@dataclass
class ResultadoFechamento:
    comissoes: list[dict]
    divergencias: list[dict]
    excecoes: list
    notas: list[dict]


def _arquivo(dados: Path, padrao: str) -> Path:
    achados = sorted(dados.glob(padrao))
    if len(achados) != 1:
        raise LayoutError(f"esperava exatamente 1 arquivo {padrao} em {dados}, achei {len(achados)}")
    return achados[0]


def checar_mes_com_dados(n_orbe_mes: int, n_ponte_mes: int, mes: str) -> list[str]:
    """Mês errado não pode gerar saídas vazias que parecem válidas. Devolve avisos (uma fonte vazia)."""
    if n_orbe_mes == 0 and n_ponte_mes == 0:
        raise LayoutError(f"nenhuma linha da Orbe nem da Ponte cai em {mes}; os arquivos são de outro mês?")
    avisos = []
    if n_orbe_mes == 0:
        avisos.append(f"Orbe: nenhuma linha em {mes}")
    if n_ponte_mes == 0:
        avisos.append(f"Ponte: nenhuma operação em {mes}")
    return avisos


def fechar(mes: str, dados: Path, saida: Path) -> ResultadoFechamento:
    cfg = carregar_defaults()
    ledger = Ledger()
    arq_taxas, arq_orbe, arq_ponte = _arquivo(dados, "02_*.xlsx"), _arquivo(dados, "01_*.csv"), _arquivo(dados, "03_*.eml")
    contratos, excecoes_taxas = ler_taxas(arq_taxas, ledger)
    registro = Registro.construir(contratos, cfg.ecs_extra, cfg.sem_contrato, cfg.aliases)
    txs = ler_orbe(arq_orbe)
    ops = ler_ponte(arq_ponte, ledger)

    txs_mes = [t for t in txs if no_mes(t.data_movimento, mes)]
    ops_mes = [o for o in ops if no_mes(o.data_contratacao, mes)]
    avisos = checar_mes_com_dados(len(txs_mes), len(ops_mes), mes)

    rastro = Rastro()
    resolvedor = Resolvedor(contratos, cfg.overrides)
    res = calcular_checkout(txs, registro, resolvedor, mes, rastro, ledger)
    div = calcular_divergencias(res.linhas, rastro)
    rem = calcular_remessa(ops, registro, resolvedor, mes, rastro, ledger=ledger)
    for e in excecoes_taxas:  # exceção de leitura da planilha: a linha da planilha é a origem
        rastro.add(e.id_saida, ARQUIVO_TAXAS, e.ref_origem, e.valor_brl)
    comissoes = res.comissoes + rem.comissoes
    notas = calcular_notas(comissoes, rastro, mes)
    excecoes = excecoes_taxas + res.excecoes + div.excecoes + rem.excecoes + notas.excecoes
    pendencias = [
        {"id_saida": e.id_saida, "tipo": e.tipo.value, "ref_origem": e.ref_origem,
         "valor_brl": e.valor_brl, "motivo": e.motivo, "quem_decide": e.quem_decide}
        for e in excecoes
    ]
    divergencias = div.divergencias + rem.divergencias

    # Valida antes de escrever: falha de invariante não deixa saída parcial.
    validar_i_r1({"comissoes_por_lojista": comissoes, "divergencias_taxa": divergencias,
                  "notas_a_emitir": notas.notas, "pendencias": pendencias}, rastro)
    validar_i_r3({ARQUIVO_ORBE: {t.id_transacao for t in txs_mes},
                  ARQUIVO_PONTE: {o.n_operacao for o in ops_mes}}, rastro)
    validar_i_d1(divergencias)
    validar_i_n1(notas.notas)

    saida.mkdir(parents=True, exist_ok=True)
    escrever_csv(saida / "comissoes_por_lojista.csv", "comissoes_por_lojista", comissoes)
    escrever_csv(saida / "divergencias_taxa.csv", "divergencias_taxa", divergencias)
    escrever_csv(saida / "notas_a_emitir.csv", "notas_a_emitir", notas.notas)
    escrever_csv(saida / "pendencias.csv", "pendencias", pendencias)
    escrever_rastro(saida / "rastro.csv", rastro)

    # Sem carimbo de data: o log também é idêntico entre duas execuções com as mesmas entradas.
    linhas_log = [
        f"fechamento {mes}",
        f"arquivos: {arq_orbe.name}, {arq_taxas.name}, {arq_ponte.name}",
        f"Orbe: {len(txs)} linha(s), {len(txs_mes)} no mês, {len(txs) - len(txs_mes)} fora do mês",
        f"Ponte: {len(ops)} linha(s), {len(ops_mes)} no mês, {len(ops) - len(ops_mes)} fora do mês",
        f"Taxas: {len(contratos)} linha(s) de contrato",
        *ledger.linhas_log(),
        *[f"AVISO: {a}" for a in avisos],
        "validação: I-R1, I-R3, I-D1, I-N1 ok",
        f"comissoes_por_lojista: {len(comissoes)} linha(s)",
        f"divergencias_taxa: {len(divergencias)} linha(s)",
        f"notas_a_emitir: {len(notas.notas)} linha(s)",
        f"pendencias: {len(pendencias)} linha(s)",
        f"rastro: {len(rastro.linhas())} linha(s)",
    ]
    (saida / "execucao.log").write_text("\n".join(linhas_log) + "\n", encoding="utf-8")
    return ResultadoFechamento(comissoes, divergencias, excecoes, notas.notas)
