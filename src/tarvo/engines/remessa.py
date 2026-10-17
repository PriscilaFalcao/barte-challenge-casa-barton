"""Motor de remessa (PRD 7.4 e 7.5): comissão sobre o spread realizado e divergência contra o contratado."""
from __future__ import annotations

import collections
from dataclasses import dataclass, field
from decimal import Decimal

from ..contracts.resolver import ContratoError, Resolvedor
from ..core.competencia import no_mes
from ..core.ledger import Ledger
from ..core.excecoes import Excecao, TipoExcecao
from ..core.ids import id_comissao, id_divergencia
from ..core.money import fmt, fmt_pct, round_money
from ..core.rastro import Rastro
from ..identity.registro import Registro
from ..ingest.ponte import ARQUIVO as ARQUIVO_PONTE
from ..ingest.ponte import OpPonte
from .divergencias import CONTRATO

STATUS_CONHECIDOS = {"APROVADO", "APROVADO C/ RESSALVA"}  # ✅ R7: a ressalva não muda nada

# Naturezas de uma contestação com a Ponte, na ordem em que aparecem no motivo.
EXCESSO, NEGATIVO, DUPLICATA = "excesso de spread", "spread negativo", "operação duplicada"


@dataclass(frozen=True)
class LinhaRemessa:
    op: OpPonte
    cnpj14: str
    comissao: Decimal
    regra_id: str  # R1, ou R4 quando o realizado inclui excesso sobre o contratado


@dataclass(frozen=True)
class _ItemContestacao:
    natureza: str
    n_op: str
    valor: Decimal
    componente: str
    regra: str
    detalhe: str


@dataclass
class ResultadoRemessa:
    comissoes: list[dict] = field(default_factory=list)
    divergencias: list[dict] = field(default_factory=list)
    excecoes: list[Excecao] = field(default_factory=list)
    linhas: list[LinhaRemessa] = field(default_factory=list)


def _pendencia(res: ResultadoRemessa, rastro: Rastro, tipo: TipoExcecao, ref: str, valor: Decimal,
               motivo: str, origens: list[tuple[str, Decimal, str]], regra: str, arq: dict[str, str]) -> None:
    """origens: (componente, valor, ref_origem) de cada linha de rastro; a soma tem que dar `valor`."""
    exc = Excecao.nova(tipo, ref, valor, motivo)
    res.excecoes.append(exc)
    for componente, v, origem in origens:
        rastro.add(exc.id_saida, arq.get(origem, ARQUIVO_PONTE), origem, v, componente, "", regra)


def _contestacoes(res: ResultadoRemessa, rastro: Rastro, mes: str, nomes: dict[str, str],
                  itens: dict[str, list[_ItemContestacao]], arq: dict[str, str]) -> None:
    """✅ Casa Barton 11h01: uma pendência por contraparte (Ponte) e por lojista, com o detalhe das operações
    anexado; é o rascunho de contestação. ⚠️ R13: valor = soma dos desvios de cada natureza, com sinal."""
    competencia = mes.replace("-", "")
    for cnpj, lista in sorted(itens.items()):
        total = sum((i.valor for i in lista), Decimal("0"))
        partes = []
        for natureza in (EXCESSO, NEGATIVO, DUPLICATA):
            do_tipo = [i for i in lista if i.natureza == natureza]
            if do_tipo:
                ops = ", ".join(sorted({i.n_op for i in do_tipo}))
                detalhes = "; ".join(sorted({i.detalhe for i in do_tipo}))
                partes.append(f"{natureza}: {len(do_tipo)} item(ns), R$ {fmt(sum((i.valor for i in do_tipo), Decimal('0')))}"
                              f" ({detalhes}) em {ops}")
        motivo = (f"Contestação com a Ponte, {nomes.get(cnpj, cnpj)} em {mes[5:]}/{mes[:4]}. "
                  + ". ".join(p[0].upper() + p[1:] for p in partes)
                  + ". Nada contestado ainda: não assumir desconto no repasse.")
        exc = Excecao.nova(TipoExcecao.CONTESTACAO_PONTE, f"{cnpj}-{competencia}", total, motivo)
        res.excecoes.append(exc)
        for i in sorted(lista, key=lambda i: (i.n_op, i.componente)):
            rastro.add(exc.id_saida, arq.get(i.n_op, ARQUIVO_PONTE), i.n_op, i.valor, i.componente, "", i.regra)


def calcular_remessa(
    ops: list[OpPonte], registro: Registro, resolvedor: Resolvedor, mes: str, rastro: Rastro,
    participacao: Decimal = Decimal("0.50"),
    tolerancia_spread_pp: Decimal = Decimal("0.01"),
    spread_negativo_em_divergencias: bool = False,
    ledger: Ledger | None = None,
) -> ResultadoRemessa:
    """Parâmetros com default documentado: `participacao` (✅ R1, 50%), `tolerancia_spread_pp` (⚠️ R11,
    ✅ aceita se escrita) e `spread_negativo_em_divergencias` (✅ V4: spread negativo não é divergência,
    porque o lojista não pagou a mais; é só contestação). Competência = data de contratação (✅ R8)."""
    res = ResultadoRemessa()
    totais: dict[str, Decimal] = collections.defaultdict(Decimal)
    nomes: dict[str, str] = {}
    nao_resolvidas: dict[str, list[tuple[OpPonte, Decimal]]] = collections.defaultdict(list)
    duplicatas: dict[str, list[OpPonte]] = collections.defaultdict(list)
    primeiras: dict[str, OpPonte] = {}
    contestar: dict[str, list[_ItemContestacao]] = collections.defaultdict(list)

    # arquivo de cada operação, para o rastro apontar para o relatório certo quando há mais de um no mês
    arq: dict[str, str] = {}
    for o in sorted(ops, key=lambda o: (o.n_operacao, o.arquivo, o.linha_fisica)):
        arq.setdefault(o.n_operacao, o.arquivo)

    def meia(o: OpPonte) -> Decimal:
        return round_money(participacao * o.spread_brl)

    for o in sorted(ops, key=lambda o: (o.n_operacao, o.arquivo, o.linha_fisica)):
        if not no_mes(o.data_contratacao, mes):
            if ledger is not None:
                ledger.ignorar("Ponte", "fora do mês", o.n_operacao)
            continue
        if o.n_operacao in primeiras:  # ✅ R6: número de operação é único; a repetição não conta
            duplicatas[o.n_operacao].append(o)
            continue
        primeiras[o.n_operacao] = o

    for n_op, o in primeiras.items():
        if o.status not in STATUS_CONHECIDOS:
            _pendencia(res, rastro, TipoExcecao.STATUS_PONTE_DESCONHECIDO, n_op, meia(o),
                       f"Status de compliance {o.status!r} não está na lista conhecida; operação fora da "
                       f"comissão até alguém definir o tratamento.", [("SPREAD", meia(o), n_op)], "R7", arq)
            continue
        entidade = registro.classificar(cnpj=o.cnpj14)
        resolvida = entidade.situacao == "LOJISTA"
        # ✅ Desbravadores: CNPJ fora do cadastro entra na comissão (a Ponte paga e a nota tem que bater com o
        # repasse) e vira pendência de cadastro para o comercial. Sem contrato, a divergência não é avaliada.
        nomes.setdefault(o.cnpj14, entidade.lojista.nome_canonico if resolvida else o.cliente or o.cnpj14)

        divergente, diferenca, contratado_pp = False, Decimal("0"), None
        aplicado_pp = o.spread_pct * 100
        if resolvida:
            try:
                contratado_pp = resolvedor.spread(o.cnpj14, o.data_contratacao).pct
                divergente = abs(aplicado_pp - contratado_pp) > tolerancia_spread_pp
                if divergente:  # R10: base é Valor ME × PTAX, e o sinal é o de D1 (aplicado − contratado)
                    diferenca = round_money(o.valor_me * o.ptax * (o.spread_pct - contratado_pp / 100))
            except ContratoError as exc:
                _pendencia(res, rastro, exc.tipo, n_op, Decimal("0.00"),
                           f"{exc.motivo}. A comissão da operação foi calculada, mas a divergência de spread "
                           f"não pôde ser avaliada.", [("SPREAD", Decimal("0.00"), n_op)], "R10", arq)

        negativo = o.spread_brl < 0
        if divergente and (not negativo or spread_negativo_em_divergencias):
            id_div = id_divergencia("REMESSA", n_op)
            res.divergencias.append({
                "id_saida": id_div, "cnpj": o.cnpj14, "linha_negocio": "REMESSA", "ref_origem": n_op,
                "taxa_contratada_pct": fmt_pct(contratado_pp), "taxa_aplicada_pct": fmt_pct(aplicado_pp),
                "diferenca_brl": diferenca, "natureza": CONTRATO,
            })
            rastro.add(id_div, arq.get(n_op, ARQUIVO_PONTE), n_op, diferenca, "SPREAD", fmt_pct(contratado_pp), "R10")

        if negativo:  # ✅ R5: fora da comissão e da nota; contestação
            valor = diferenca if divergente else o.spread_brl
            contra = f"contra {fmt_pct(contratado_pp)}% contratado" if contratado_pp is not None else "sem contrato"
            contestar[o.cnpj14].append(_ItemContestacao(
                NEGATIVO, n_op, valor, "SPREAD", "R9",
                f"{o.observacao or 'sem observação'}; fora da comissão e da nota; valor = desvio {contra}"))
            continue

        comissao = meia(o)
        regra = "R4" if divergente else "R1"
        totais[o.cnpj14] += comissao
        res.linhas.append(LinhaRemessa(o, o.cnpj14, comissao, regra))
        rastro.add(id_comissao("REMESSA", o.cnpj14, mes), o.arquivo, n_op, comissao, "SPREAD",
                   fmt_pct(participacao * 100), regra)
        if not resolvida:
            nao_resolvidas[o.cnpj14].append((o, comissao))
        if divergente:  # ✅ R3/R4/R9: comissão pelo realizado e contestação pelo valor cheio
            contestar[o.cnpj14].append(_ItemContestacao(
                EXCESSO, n_op, diferenca, "SPREAD", "R9",
                f"aplicado x contratado {fmt_pct(contratado_pp)}%; o excesso entra na nota pelo realizado e "
                f"o ajuste vem no mês em que a Ponte devolver"))

    for n_op, extras in sorted(duplicatas.items()):
        original = primeiras[n_op]
        igual = all((e.spread_brl, e.valor_me, e.cnpj14) == (original.spread_brl, original.valor_me, original.cnpj14)
                    for e in extras)
        for e in extras:
            contestar[original.cnpj14].append(_ItemContestacao(
                DUPLICATA, n_op, meia(e),
                f"DUPLICATA-L{e.linha_fisica}" if e.arquivo == original.arquivo
                else f"DUPLICATA-{e.arquivo}-L{e.linha_fisica}", "R6",
                f"{'valores idênticos' if igual else 'valores diferentes'} da primeira; conta uma vez; "
                f"valor = comissão inflada se o total da Ponte fosse aceito; Ponte deve corrigir o relatório"))

    _contestacoes(res, rastro, mes, nomes, contestar, arq)

    for cnpj, grupo in sorted(nao_resolvidas.items()):
        valor = sum((c for _, c in grupo), Decimal("0"))
        _pendencia(res, rastro, TipoExcecao.ENTIDADE_NAO_RESOLVIDA, cnpj, valor,
                   f"CNPJ {cnpj} ({nomes[cnpj]}) da Ponte não está no cadastro de lojistas ({len(grupo)} "
                   f"operação(ões)). Comissão calculada e incluída na nota da Ponte; cadastrar o lojista. "
                   f"Divergência de spread não avaliada (sem contrato).",
                   [("SPREAD", c, o.n_operacao) for o, c in grupo], "R1", arq)

    for cnpj14 in sorted(totais):
        res.comissoes.append({
            "id_saida": id_comissao("REMESSA", cnpj14, mes), "cnpj": cnpj14, "lojista": nomes[cnpj14],
            "linha_negocio": "REMESSA", "comissao_brl": totais[cnpj14],
        })
    res.excecoes.sort(key=lambda e: e.id_saida)
    res.divergencias.sort(key=lambda d: d["id_saida"])
    return res
