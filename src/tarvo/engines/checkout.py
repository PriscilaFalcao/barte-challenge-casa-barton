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
        rastro.add(exc.id_saida, t.arquivo, t.id_transacao, t.valor_taxa)


def _alerta_antecipacao(res: ResultadoCheckout, rastro: Rastro, ec: str, nome: str | None,
                        txs: list[OrbeTx], sem_contrato: bool, novo: bool) -> None:
    """✅ Helena (P8): antecipação acima do que o lojista vendeu "não deveria acontecer"; alerta para ela e o
    comercial, "ainda mais com a Atlas sem contrato", e o que a preocupa é "lojista novo, sem histórico,
    antecipando alto". ⚠️ Critério nosso (ela deixou a escolha): alerta quando o lojista está sem contrato ou é
    novo (sem vendas em meses anteriores) E antecipou, em algum dia, mais do que vendeu no mês até o dia. Nos
    demais, antecipar acima das vendas do mês é normal (antecipam vendas de meses anteriores, fora do arquivo).
    Dispara pelo pico (o risco existiu quando o dinheiro foi adiantado) e cita as reversões. Valor = antecipado
    líquido no mês (antecipações − reversões), com cada linha no rastro. Não muda nenhum número."""
    antecip = [t for t in txs if t.tipo in ("ANTECIPACAO", "REVERSAO_ANTECIPACAO")]
    pico = None  # (dia, antecipado no dia, vendas líquidas até o dia)
    for dia in sorted({t.data_movimento for t in antecip if t.tipo == "ANTECIPACAO"}):
        no_dia = sum((t.valor_bruto for t in antecip if t.tipo == "ANTECIPACAO" and t.data_movimento == dia),
                     Decimal("0"))
        vendas = sum((t.valor_bruto for t in txs if t.tipo in ("VENDA", "ESTORNO") and t.data_movimento <= dia),
                     Decimal("0"))
        if no_dia > vendas and (pico is None or no_dia - vendas > pico[1] - pico[2]):
            pico = (dia, no_dia, vendas)
    if pico is None:
        return
    liquido = sum((t.valor_bruto for t in antecip), Decimal("0"))
    quem = ("novo e sem contrato" if sem_contrato and novo else "sem contrato" if sem_contrato
            else "novo (sem vendas em meses anteriores)")
    detalhe = (f" Em {pico[0].strftime('%d/%m')} antecipou R$ {fmt(pico[1])} com R$ {fmt(pico[2])} de vendas "
               f"líquidas no mês até o dia.")
    exc = Excecao.nova(
        TipoExcecao.ALERTA_ANTECIPACAO, ec, liquido,
        f"{nome or 'Lojista'} (EC {ec}), {quem}, antecipou R$ {fmt(liquido)} líquidos no mês "
        f"({len(antecip)} linha(s), reversões abatidas).{detalhe} Não há trava de antecipação; avisar o financeiro "
        f"e o comercial.")
    res.excecoes.append(exc)
    for t in sorted(antecip, key=lambda t: t.id_transacao):
        rastro.add(exc.id_saida, t.arquivo, t.id_transacao, t.valor_bruto, "ANTECIPACAO", "", "P8")


def calcular_checkout(txs: list[OrbeTx], registro: Registro, resolvedor: Resolvedor,
                      mes: str, rastro: Rastro, ledger: Ledger | None = None,
                      recuperar: dict[str, frozenset[str]] | None = None,
                      ecs_com_historico: set[str] | None = None) -> ResultadoCheckout:
    """`recuperar`: EC -> meses (AAAA-MM) cujas linhas da Orbe entram neste fechamento além das do próprio mês.
    ✅ Helena 11h41: taxa confirmada pelo comercial vale desde o começo, e o mês seguinte fatura o que ficou
    pendente. Só vale se o EC já tem contrato; sem contrato, as linhas continuam fora (pendência SEM_CONTRATO)."""
    recuperar = recuperar or {}

    def do_fechamento(t: OrbeTx) -> bool:
        return no_mes(t.data_movimento, mes) or t.data_movimento.strftime("%Y-%m") in recuperar.get(
            t.cod_estabelecimento, ())

    res = ResultadoCheckout()
    sem_contrato: dict[str, list[OrbeTx]] = collections.defaultdict(list)
    nao_resolvidas: dict[str, list[OrbeTx]] = collections.defaultdict(list)
    nomes: dict[str, str] = {}
    totais: dict[str, Decimal] = collections.defaultdict(Decimal)
    linhas_do_lojista: dict[str, list[LinhaCheckout]] = collections.defaultdict(list)

    # Ordem fixa: o resultado não depende da ordem das linhas de entrada.
    for t in txs:
        if not do_fechamento(t) and ledger is not None:
            ledger.ignorar("Orbe", "fora do mês", t.id_transacao)
    for tx in sorted((t for t in txs if do_fechamento(t)), key=lambda t: t.id_transacao):
        entidade = registro.classificar(ec=tx.cod_estabelecimento)
        recuperada = not no_mes(tx.data_movimento, mes)
        if entidade.situacao == "SEM_CONTRATO":
            if not recuperada:  # linha de mês anterior de quem continua sem contrato não é deste fechamento
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
        regra = _regra(tx, taxa, mes) + ("+RECUP" if recuperada else "")
        linha = LinhaCheckout(tx, loj.cnpj14, produto, componente, taxa, regra, comissao)
        res.linhas.append(linha)
        nomes[loj.cnpj14] = loj.nome_canonico
        totais[loj.cnpj14] += comissao
        id_saida = id_comissao("CHECKOUT", loj.cnpj14, mes)
        rastro.add(id_saida, tx.arquivo, tx.id_transacao, comissao, componente,
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
                   f"informar a taxa. Valor = soma da taxa cobrada pela Orbe nas {len(grupo)} linhas (só dimensiona). "
                   f"Quando o comercial confirmar, a taxa vale desde o início e estas linhas entram no fechamento "
                   f"daquele mês: puxar do rastro deste mês.")
    anteriores = {t.cod_estabelecimento for t in txs
                  if t.tipo == "VENDA" and t.data_movimento.strftime("%Y-%m") < mes}
    conhecidos = None if ecs_com_historico is None and not anteriores else (ecs_com_historico or set()) | anteriores
    do_mes: dict[str, list[OrbeTx]] = collections.defaultdict(list)
    for t in txs:
        if no_mes(t.data_movimento, mes):
            do_mes[t.cod_estabelecimento].append(t)
    for ec, grupo in sorted(do_mes.items()):
        entidade = registro.classificar(ec=ec)
        if entidade.situacao == "NAO_RESOLVIDO":
            continue
        sem = entidade.situacao == "SEM_CONTRATO"
        novo = conhecidos is not None and ec not in conhecidos
        if sem or novo:
            nome = entidade.nome if sem else entidade.lojista.nome_canonico
            _alerta_antecipacao(res, rastro, ec, nome, grupo, sem, novo)
    for ec, grupo in sorted(nao_resolvidas.items()):
        _pendencia(res, rastro, TipoExcecao.ENTIDADE_NAO_RESOLVIDA, ec, grupo,
                   f"EC {ec} não está no cadastro de lojistas ({len(grupo)} linhas, "
                   f"soma da taxa Orbe R$ {fmt(sum((t.valor_taxa for t in grupo), Decimal('0')))}); sem comissão.")
    res.excecoes.sort(key=lambda e: e.id_saida)
    return res
