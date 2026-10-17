"""Rascunhos de contestação (✅ Helena, Casa Barton 11h01: a pendência por contraparte e por lojista, com o
detalhe das transações, "é o que vira o rascunho de contestação").

Um texto por contraparte, pronto para o Financeiro revisar e enviar: Ponte Câmbio (excesso de spread, spread
negativo, operação duplicada) e Orbe (taxa aplicada acima da contratada). Nada é enviado pela solução: quem
decide contestar é o Financeiro. Tudo vem das pendências e do rastro já calculados; este módulo só apresenta.

Fora das contestações, por serem decisão interna e não cobrança de terceiro: a devolução da Casa do Estudante
(a Orbe cobrou certo pelo que sabia) e o lojista sem contrato.
"""
from __future__ import annotations

import collections
from decimal import Decimal

from ..core.excecoes import TipoExcecao
from ..core.money import fmt_pct
from ..core.rastro import LinhaRastro
from ..ingest.orbe import OrbeTx
from ..ingest.ponte import OpPonte
from .resumo import brl

PONTE, ORBE = "Ponte Câmbio S.A.", "Orbe Adquirência S.A."
ZERO = Decimal("0")


def _cnpj(c: str) -> str:
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else c


def _num(v: Decimal, casas: int = 2) -> str:
    """Número em formato brasileiro (1.234,56), para leitura."""
    inteiro, _, dec = f"{v:,.{casas}f}".partition(".")
    return inteiro.replace(",", ".") + (f",{dec}" if dec else "")


def _pct(v: Decimal) -> str:
    return fmt_pct(v).replace(".", ",") + "%"


_MODALIDADE = {"CREDITO A VISTA": "Crédito à vista", "CREDITO PARCELADO": "Crédito parcelado", "DEBITO": "Débito",
               "PIX": "Pix"}


def _dia(d) -> str:
    return d.strftime("%d/%m/%Y")


def _tabela(cab: list[str], linhas: list[list[str]]) -> list[str]:
    return ["| " + " | ".join(cab) + " |", "|" + "|".join("---" for _ in cab) + "|",
            *["| " + " | ".join(l) + " |" for l in linhas], ""]


def _pp(op: OpPonte, desvio: Decimal) -> Decimal:
    """Spread contratado (em pontos percentuais) que explica o desvio: desvio = ME × PTAX × (aplicado − contratado)."""
    base = op.valor_me * op.ptax
    return ((op.spread_pct - desvio / base) * 100).quantize(Decimal("0.01")) if base else ZERO


def _ponte(mes: str, pendencias: list[dict], rastro: dict[str, list[LinhaRastro]], ops: list[OpPonte],
           nomes: dict[str, str]) -> list[str]:
    pend = sorted((p for p in pendencias if p["tipo"] == TipoExcecao.CONTESTACAO_PONTE.value),
                  key=lambda p: p["ref_origem"])
    if not pend:
        return []
    por_op: dict[str, OpPonte] = {}
    for o in sorted(ops, key=lambda o: (o.n_operacao, o.arquivo, o.linha_fisica)):
        por_op.setdefault(o.n_operacao, o)
    totais = {"excesso": ZERO, "negativo": ZERO, "duplicata": ZERO}
    blocos: list[str] = []
    for p in pend:
        cnpj = p["ref_origem"].split("-")[0]
        excesso, negativo, duplicata = [], [], []
        for l in sorted(rastro.get(p["id_saida"], []), key=lambda l: l.ref_origem):
            o = por_op.get(l.ref_origem)
            if o is None:  # referência fora do relatório lido: não inventa detalhe
                continue
            if l.regra_id == "R6":
                duplicata.append((o, l.valor))
            elif o.spread_brl < 0:
                negativo.append((o, l.valor))
            else:
                excesso.append((o, l.valor))
        blocos += [f"### {nomes.get(cnpj, cnpj)} (CNPJ {_cnpj(cnpj)})", ""]
        if excesso:
            soma = sum((v for _, v in excesso), ZERO)
            totais["excesso"] += soma
            blocos += ["**Spread aplicado acima do contratado.** O lojista pagou a mais; o valor é o integral, "
                       "não a nossa metade.", ""]
            blocos += _tabela(["Operação", "Contratação", "Moeda", "Valor ME", "PTAX", "Spread contratado",
                               "Spread aplicado", "Diferença"],
                              [[o.n_operacao, _dia(o.data_contratacao), o.moeda, _num(o.valor_me), _num(o.ptax, 4),
                                _pct(_pp(o, v)), _pct(o.spread_pct * 100), brl(v)]
                               for o, v in excesso])
            blocos += [f"Subtotal: **{brl(soma)}** em {len(excesso)} operação(ões).", ""]
        if negativo:
            soma = sum((-v for _, v in negativo), ZERO)
            totais["negativo"] += soma
            blocos += ["**Spread negativo.** A taxa travada no pedido (D-1) deveria ter sido honrada: pedimos a "
                       "diferença até o spread contratado. O spread do relatório é o que aconteceu.", ""]
            blocos += _tabela(["Operação", "Contratação", "Spread no relatório", "Spread contratado",
                               "Diferença a repor até o contrato", "Observação"],
                              [[o.n_operacao, _dia(o.data_contratacao), brl(o.spread_brl), _pct(_pp(o, v)),
                                brl(-v), o.observacao or "—"] for o, v in negativo])
            blocos += [f"Subtotal: **{brl(soma)}** em {len(negativo)} operação(ões).", ""]
        if duplicata:
            soma = sum((v for _, v in duplicata), ZERO)
            totais["duplicata"] += soma
            blocos += ["**Operação duplicada no relatório.** O mesmo número de operação aparece mais de uma vez; "
                       "contamos uma só. Pedimos a correção do relatório.", ""]
            blocos += _tabela(["Operação", "Contratação", "Spread no relatório (cada linha)",
                               "Participação da Tarvo inflada se o total fosse aceito"],
                              [[o.n_operacao, _dia(o.data_contratacao), brl(o.spread_brl), brl(v)]
                               for o, v in duplicata])
    cab = [f"## Ponte Câmbio: contestação da competência {mes[5:]}/{mes[:4]}", "",
           f"**Para:** Backoffice Parceiros, {PONTE}", "**De:** Financeiro, Tarvo Pagamentos", "",
           "Prezados, ao conferir o relatório mensal de operações da competência "
           f"{mes[5:]}/{mes[:4]}, encontramos os itens abaixo. Pedimos a revisão e o ajuste, que "
           "entendemos vir como linha de crédito ou débito no relatório do mês seguinte, com a observação "
           "\"AJUSTE REF\" e o número da operação original.", "",
           *_tabela(["Natureza", "Valor"],
                    [["Spread aplicado acima do contratado", brl(totais["excesso"])],
                     ["Spread negativo (diferença até o contrato)", brl(totais["negativo"])],
                     ["Participação da Tarvo inflada pela duplicidade", brl(totais["duplicata"])]])]
    return cab + blocos


def _orbe(mes: str, pendencias: list[dict], rastro: dict[str, list[LinhaRastro]], txs: list[OrbeTx],
          divergencias: list[dict], nomes: dict[str, str]) -> list[str]:
    pend = sorted((p for p in pendencias if p["tipo"] == TipoExcecao.DIVERGENCIA_ORBE.value),
                  key=lambda p: p["ref_origem"])
    if not pend:
        return []
    por_id = {t.id_transacao: t for t in txs}
    contratada = {d["ref_origem"]: d["taxa_contratada_pct"] for d in divergencias if d["linha_negocio"] == "CHECKOUT"}
    total = ZERO
    blocos: list[str] = []
    for p in pend:
        cnpj = p["ref_origem"].split("-")[0]
        linhas = sorted(rastro.get(p["id_saida"], []), key=lambda l: l.ref_origem)
        linhas = [l for l in linhas if l.ref_origem in por_id]  # só o que está nos arquivos lidos
        a_mais = sum((l.valor for l in linhas if l.valor > 0), ZERO)
        estornos = sum((l.valor for l in linhas if l.valor < 0), ZERO)
        liquido = a_mais + estornos
        total += liquido
        blocos += [f"### {nomes.get(cnpj, cnpj)} (CNPJ {_cnpj(cnpj)})", "",
                   f"{len(linhas)} transação(ões): {brl(a_mais)} cobrados a mais, {brl(estornos)} em estornos "
                   f"(venda e estorno se anulam). **Diferença líquida: {brl(liquido)}.**", ""]
        blocos += _tabela(["Transação", "Movimento", "Tipo", "Modalidade", "Valor bruto", "Taxa aplicada",
                           "Taxa contratada", "Diferença"],
                          [[l.ref_origem, _dia((t := por_id[l.ref_origem]).data_movimento),
                            t.tipo.capitalize() + (f" (ref. {t.id_referencia})" if t.id_referencia else ""),
                            _MODALIDADE.get(t.modalidade, t.modalidade.capitalize()) + (f" {t.qtd_parcelas}x" if t.qtd_parcelas and t.qtd_parcelas > 1
                                                          else ""),
                            brl(t.valor_bruto), _pct(t.taxa_aplicada_pct),
                            (contratada.get(l.ref_origem, "—").replace(".", ",") + "%"), brl(l.valor)] for l in linhas])
    cab = [f"## Orbe: contestação da competência {mes[5:]}/{mes[:4]}", "",
           f"**Para:** {ORBE}", "**De:** Financeiro, Tarvo Pagamentos", "",
           "Prezados, identificamos transações em que a taxa aplicada difere da taxa contratada pelo "
           f"lojista. Pedimos a devolução da diferença líquida de **{brl(total)}**, já com os estornos abatidos "
           "(a venda e o estorno se anulam; cobramos só o que sobrou).", ""]
    return cab + blocos


def _fora(pendencias: list[dict], nomes: dict[str, str]) -> list[str]:
    linhas = []
    for p in pendencias:
        cnpj = p["ref_origem"].split("-")[0]
        if p["tipo"] == TipoExcecao.DEVOLUCAO_LOJISTA.value:
            linhas.append(f"- **{nomes.get(cnpj, cnpj)}**: devolução ao lojista de {brl(Decimal(str(p['valor_brl'])))}. "
                          "A Orbe cobrou pelo que sabia (a condição comercial não foi informada a ela); é decisão "
                          "interna, com o Comercial, e não entra na cobrança à Orbe.")
        elif p["tipo"] == TipoExcecao.SEM_CONTRATO.value:
            linhas.append(f"- **EC {p['ref_origem']}** sem contrato: não há taxa contra a qual contestar; aguarda o "
                          "Comercial.")
    return ["## Fora das contestações (decisão interna)", "", *linhas, ""] if linhas else []


def gerar_rascunhos(mes: str, pendencias: list[dict], rastro: list[LinhaRastro], ops: list[OpPonte],
                    txs: list[OrbeTx], divergencias: list[dict], nomes: dict[str, str]) -> str:
    por_id: dict[str, list[LinhaRastro]] = collections.defaultdict(list)
    for l in rastro:
        por_id[l.id_saida].append(l)
    partes = _ponte(mes, pendencias, por_id, ops, nomes) + _orbe(mes, pendencias, por_id, txs, divergencias, nomes)
    topo = [f"# Rascunhos de contestação, competência {mes[5:]}/{mes[:4]}", "",
            "> **Rascunho, não enviado.** Quem decide contestar é o Financeiro. Cada valor aponta para as linhas "
            "de origem no `rastro.csv`, pelo `id_saida` da pendência correspondente.", ""]
    corpo = partes or ["Nenhuma contestação neste mês.", ""]
    return "\n".join(topo + corpo + _fora(pendencias, nomes)).rstrip() + "\n"
