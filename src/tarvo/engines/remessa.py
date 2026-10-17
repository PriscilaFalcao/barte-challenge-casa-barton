"""Motor de remessa (PRD 7.4 e 7.5): comissão sobre o spread realizado e divergência contra o contratado."""
from __future__ import annotations

import collections
from dataclasses import dataclass, field
from decimal import Decimal

from ..contracts.resolver import ContratoError, Resolvedor
from ..core.excecoes import Excecao, TipoExcecao
from ..core.ids import id_comissao, id_divergencia
from ..core.money import fmt, fmt_pct, round_money
from ..core.rastro import Rastro
from ..identity.registro import Registro
from ..ingest.ponte import ARQUIVO as ARQUIVO_PONTE
from ..ingest.ponte import OpPonte

STATUS_CONHECIDOS = {"APROVADO", "APROVADO C/ RESSALVA"}  # ✅ R7: a ressalva não muda nada


@dataclass(frozen=True)
class LinhaRemessa:
    op: OpPonte
    cnpj14: str
    comissao: Decimal
    regra_id: str  # R1, ou R4 quando o realizado inclui excesso sobre o contratado


@dataclass
class ResultadoRemessa:
    comissoes: list[dict] = field(default_factory=list)
    divergencias: list[dict] = field(default_factory=list)
    excecoes: list[Excecao] = field(default_factory=list)
    linhas: list[LinhaRemessa] = field(default_factory=list)


def _pendencia(res: ResultadoRemessa, rastro: Rastro, tipo: TipoExcecao, ref: str, valor: Decimal,
               motivo: str, origens: list[tuple[str, Decimal, str]], regra: str) -> None:
    """origens: (componente, valor, ref_origem) de cada linha de rastro; a soma tem que dar `valor`.

    Mesmo tipo e mesma operação (ex.: duplicada e também divergente) viram UMA pendência: o id é
    determinístico e a Helena decide a operação de uma vez. Valor e motivo se somam, o rastro ganha as linhas.
    """
    nova = Excecao.nova(tipo, ref, valor, motivo)
    for i, existente in enumerate(res.excecoes):
        if existente.id_saida == nova.id_saida:
            res.excecoes[i] = Excecao(tipo, ref, existente.valor_brl + valor,
                                      f"{existente.motivo} Também: {motivo}", existente.quem_decide)
            break
    else:
        res.excecoes.append(nova)
    for componente, v, origem in origens:
        rastro.add(nova.id_saida, ARQUIVO_PONTE, origem, v, componente, "", regra)


def calcular_remessa(
    ops: list[OpPonte], registro: Registro, resolvedor: Resolvedor, mes: str, rastro: Rastro,
    participacao: Decimal = Decimal("0.50"),
    tolerancia_spread_pp: Decimal = Decimal("0.01"),
    spread_negativo_em_divergencias: bool = True,
) -> ResultadoRemessa:
    """Parâmetros ⚠️ com default documentado: `participacao` (✅ R1, 50%), `tolerancia_spread_pp` (⚠️ R11,
    🟡 V9) e `spread_negativo_em_divergencias` (⚠️ R12, 🟡 V4). Competência = data de contratação (✅ R8)."""
    res = ResultadoRemessa()
    totais: dict[str, Decimal] = collections.defaultdict(Decimal)
    nomes: dict[str, str] = {}
    nao_resolvidas: dict[str, list[OpPonte]] = collections.defaultdict(list)
    duplicatas: dict[str, list[OpPonte]] = collections.defaultdict(list)
    primeiras: dict[str, OpPonte] = {}

    def meia(o: OpPonte) -> Decimal:
        return round_money(participacao * o.spread_brl)

    for o in sorted(ops, key=lambda o: (o.n_operacao, o.linha_fisica)):
        if o.data_contratacao.strftime("%Y-%m") != mes:
            continue
        if o.n_operacao in primeiras:  # ✅ R6: número de operação é único; a repetição não conta
            duplicatas[o.n_operacao].append(o)
            continue
        primeiras[o.n_operacao] = o

    for n_op, o in primeiras.items():
        if o.status not in STATUS_CONHECIDOS:
            _pendencia(res, rastro, TipoExcecao.STATUS_PONTE_DESCONHECIDO, n_op, meia(o),
                       f"Status de compliance {o.status!r} não está na lista conhecida; operação fora da "
                       f"comissão até alguém definir o tratamento.", [("SPREAD", meia(o), n_op)], "R7")
            continue
        entidade = registro.classificar(cnpj=o.cnpj14)
        if entidade.situacao != "LOJISTA":
            nao_resolvidas[o.cnpj14].append(o)
            continue
        loj = entidade.lojista
        nomes[loj.cnpj14] = loj.nome_canonico

        divergente, diferenca, contratado_pp = False, Decimal("0"), None
        aplicado_pp = o.spread_pct * 100
        try:
            contratado_pp = resolvedor.spread(loj.cnpj14, o.data_contratacao).pct
            divergente = abs(aplicado_pp - contratado_pp) > tolerancia_spread_pp
            if divergente:  # R10: base é Valor ME × PTAX, e o sinal é o de D1 (aplicado − contratado)
                diferenca = round_money(o.valor_me * o.ptax * (o.spread_pct - contratado_pp / 100))
        except ContratoError as exc:
            _pendencia(res, rastro, exc.tipo, n_op, Decimal("0.00"),
                       f"{exc.motivo}. A comissão da operação foi calculada, mas a divergência de spread "
                       f"não pôde ser avaliada.", [("SPREAD", Decimal("0.00"), n_op)], "R10")

        negativo = o.spread_brl < 0
        if divergente and (not negativo or spread_negativo_em_divergencias):
            id_div = id_divergencia("REMESSA", n_op)
            res.divergencias.append({
                "id_saida": id_div, "cnpj": loj.cnpj14, "linha_negocio": "REMESSA", "ref_origem": n_op,
                "taxa_contratada_pct": fmt_pct(contratado_pp), "taxa_aplicada_pct": fmt_pct(aplicado_pp),
                "diferenca_brl": diferenca,
            })
            rastro.add(id_div, ARQUIVO_PONTE, n_op, diferenca, "SPREAD", fmt_pct(contratado_pp), "R10")

        if negativo:  # ✅ R5: fora da comissão e da nota; contestação
            valor = diferenca if divergente else o.spread_brl
            _pendencia(res, rastro, TipoExcecao.CONTESTACAO_PONTE, n_op, valor,
                       f"Spread realizado negativo (R$ {fmt(o.spread_brl)}, {o.observacao or 'sem observação'}); "
                       f"fora da comissão e da nota. Valor = desvio contra o contrato "
                       f"({fmt_pct(contratado_pp) if contratado_pp is not None else '?'}%). Contestar com a Ponte.",
                       [("SPREAD", valor, n_op)], "R9")
            continue

        comissao = meia(o)
        regra = "R4" if divergente else "R1"
        totais[loj.cnpj14] += comissao
        res.linhas.append(LinhaRemessa(o, loj.cnpj14, comissao, regra))
        rastro.add(id_comissao("REMESSA", loj.cnpj14, mes), ARQUIVO_PONTE, n_op, comissao, "SPREAD",
                   fmt_pct(participacao * 100), regra)
        if divergente:  # ✅ R3/R4/R9: comissão pelo realizado e pendência de contestação pelo valor cheio
            _pendencia(res, rastro, TipoExcecao.CONTESTACAO_PONTE, n_op, diferenca,
                       f"Spread aplicado {fmt_pct(aplicado_pp)}% contra {fmt_pct(contratado_pp)}% contratado. "
                       f"O excesso entra na nota de setembro (realizado); contestar com a Ponte e ajustar no mês "
                       f"em que ela devolver.", [("SPREAD", diferenca, n_op)], "R9")

    for n_op, extras in sorted(duplicatas.items()):
        original = primeiras[n_op]
        igual = all((e.spread_brl, e.valor_me, e.cnpj14) == (original.spread_brl, original.valor_me, original.cnpj14)
                    for e in extras)
        valor = sum((meia(e) for e in extras), Decimal("0"))
        _pendencia(res, rastro, TipoExcecao.CONTESTACAO_PONTE, n_op, valor,
                   f"Nº de operação duplicado no relatório da Ponte ({len(extras)} repetição(ões), "
                   f"{'valores idênticos' if igual else 'valores diferentes'} da primeira). Conta uma vez; "
                   f"comissão inflada de R$ {fmt(valor)} na lista para a Ponte corrigir o relatório.",
                   [(f"DUPLICATA-L{e.linha_fisica}", meia(e), n_op) for e in extras], "R6")

    for cnpj, grupo in sorted(nao_resolvidas.items()):
        valor = sum((meia(e) for e in grupo), Decimal("0"))
        _pendencia(res, rastro, TipoExcecao.ENTIDADE_NAO_RESOLVIDA, cnpj, valor,
                   f"CNPJ {cnpj} da Ponte não está no cadastro de lojistas ({len(grupo)} operação(ões)); "
                   f"fora da comissão.", [("SPREAD", meia(e), e.n_operacao) for e in grupo], "R1")

    for cnpj14 in sorted(totais):
        res.comissoes.append({
            "id_saida": id_comissao("REMESSA", cnpj14, mes), "cnpj": cnpj14, "lojista": nomes[cnpj14],
            "linha_negocio": "REMESSA", "comissao_brl": totais[cnpj14],
        })
    res.excecoes.sort(key=lambda e: e.id_saida)
    res.divergencias.sort(key=lambda d: d["id_saida"])
    return res
