"""Motor de checkout (PRD 7.3): comissão por transação da Orbe, agregada por lojista, com rastro."""
from __future__ import annotations

import collections
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from ..contracts.resolver import ContratoError, Resolvedor, TaxaResolvida, produto_de
from ..core.competencia import no_mes
from ..core.ledger import Ledger
from ..core.excecoes import Excecao, TipoExcecao
from ..core.ids import id_comissao
from ..core.money import fmt, fmt_pct, round_money
from ..core.rastro import Rastro
from ..identity.registro import Registro
from ..ingest.orbe import ARQUIVO as ARQUIVO_ORBE
from ..ingest.orbe import OrbeTx


@dataclass(frozen=True)
class LinhaCheckout:
    """Uma transação calculada. Alimenta o rastro, as divergências (B3) e as notas (B5)."""
    tx: OrbeTx
    cnpj14: str
    produto: str
    componente: str  # MDR | ANTECIPACAO
    taxa: TaxaResolvida
    regra_id: str
    comissao: Decimal


@dataclass
class ResultadoCheckout:
    comissoes: list[dict] = field(default_factory=list)
    linhas: list[LinhaCheckout] = field(default_factory=list)
    excecoes: list[Excecao] = field(default_factory=list)


def _produto_e_data(tx: OrbeTx) -> tuple[str, str, date]:
    """(produto, componente, data cuja taxa vale). C3/C4/C6: estorno e reversão usam a data original."""
    if tx.tipo == "ANTECIPACAO":
        return "ANTECIPACAO", "ANTECIPACAO", tx.data_movimento
    if tx.tipo == "REVERSAO_ANTECIPACAO":
        return "ANTECIPACAO", "ANTECIPACAO", _data_original(tx)
    produto = produto_de(tx.modalidade, tx.qtd_parcelas)
    return produto, "MDR", tx.data_movimento if tx.tipo == "VENDA" else _data_original(tx)


def _data_original(tx: OrbeTx) -> date:
    if tx.data_venda_original is None:
        raise ContratoError(f"{tx.tipo} {tx.id_transacao} sem data_venda_original")
    return tx.data_venda_original


def _regra(tx: OrbeTx, taxa: TaxaResolvida, mes: str) -> str:
    if taxa.regra_id not in ("PLANILHA", "R2"):
        return taxa.regra_id  # override (ex.: C8) explica o número melhor que a regra genérica
    if tx.tipo == "ESTORNO":
        historico = tx.data_venda_original.strftime("%Y-%m") < mes
        return "C3-HISTORICO" if historico else "C3"
    return "C4" if tx.tipo in ("ANTECIPACAO", "REVERSAO_ANTECIPACAO") else "C1"


def _pendencia(res: ResultadoCheckout, rastro: Rastro, tipo: TipoExcecao, ref: str,
               txs: list[OrbeTx], motivo: str) -> None:
    exc = Excecao.nova(tipo, ref, sum((t.valor_taxa for t in txs), Decimal("0")), motivo)
    res.excecoes.append(exc)
    for t in txs:
        rastro.add(exc.id_saida, ARQUIVO_ORBE, t.id_transacao, t.valor_taxa)


def calcular_checkout(txs: list[OrbeTx], registro: Registro, resolvedor: Resolvedor,
                      mes: str, rastro: Rastro, ledger: Ledger | None = None) -> ResultadoCheckout:
    res = ResultadoCheckout()
    sem_contrato: dict[str, list[OrbeTx]] = collections.defaultdict(list)
    nao_resolvidas: dict[str, list[OrbeTx]] = collections.defaultdict(list)
    nomes: dict[str, str] = {}
    totais: dict[str, Decimal] = collections.defaultdict(Decimal)
    linhas_do_lojista: dict[str, list[LinhaCheckout]] = collections.defaultdict(list)

    # Ordem fixa: o resultado não depende da ordem das linhas de entrada.
    for t in txs:
        if not no_mes(t.data_movimento, mes) and ledger is not None:
            ledger.ignorar("Orbe", "fora do mês", t.id_transacao)
    for tx in sorted((t for t in txs if no_mes(t.data_movimento, mes)), key=lambda t: t.id_transacao):
        entidade = registro.classificar(ec=tx.cod_estabelecimento)
        if entidade.situacao == "SEM_CONTRATO":
            sem_contrato[tx.cod_estabelecimento].append(tx)
            continue
        if entidade.situacao == "NAO_RESOLVIDO":
            nao_resolvidas[tx.cod_estabelecimento].append(tx)
            continue
        loj = entidade.lojista
        try:
            produto, componente, dia = _produto_e_data(tx)
            taxa = resolvedor.taxa(loj.cnpj14, produto, dia)
        except ContratoError as exc:
            _pendencia(res, rastro, exc.tipo, tx.id_transacao, [tx], exc.motivo)
            continue
        # C1/C2: base é o valor bruto assinado × taxa contratada; nunca o valor_taxa da Orbe.
        comissao = round_money(tx.valor_bruto * taxa.pct / 100)
        linha = LinhaCheckout(tx, loj.cnpj14, produto, componente, taxa, _regra(tx, taxa, mes), comissao)
        res.linhas.append(linha)
        nomes[loj.cnpj14] = loj.nome_canonico
        totais[loj.cnpj14] += comissao
        id_saida = id_comissao("CHECKOUT", loj.cnpj14, mes)
        rastro.add(id_saida, ARQUIVO_ORBE, tx.id_transacao, comissao, componente,
                   fmt_pct(taxa.pct), linha.regra_id)

    for cnpj14 in sorted(totais):
        res.comissoes.append({
            "id_saida": id_comissao("CHECKOUT", cnpj14, mes), "cnpj": cnpj14, "lojista": nomes[cnpj14],
            "linha_negocio": "CHECKOUT", "comissao_brl": totais[cnpj14],
        })
    for ec, grupo in sorted(sem_contrato.items()):
        nome = registro.classificar(ec=ec).nome
        _pendencia(res, rastro, TipoExcecao.SEM_CONTRATO, ec, grupo,
                   f"{nome} (EC {ec}) sem contrato: comissão não calculada e sem nota até o comercial "
                   f"informar a taxa. Valor = soma da taxa cobrada pela Orbe nas {len(grupo)} linhas.")
    for ec, grupo in sorted(nao_resolvidas.items()):
        _pendencia(res, rastro, TipoExcecao.ENTIDADE_NAO_RESOLVIDA, ec, grupo,
                   f"EC {ec} não está no cadastro de lojistas ({len(grupo)} linhas, "
                   f"soma da taxa Orbe R$ {fmt(sum((t.valor_taxa for t in grupo), Decimal('0')))}); sem comissão.")
    res.excecoes.sort(key=lambda e: e.id_saida)
    return res
