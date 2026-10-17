"""Motor de divergências de checkout (PRD 7.5): taxa aplicada pela Orbe contra taxa contratada."""
from __future__ import annotations

import collections
from dataclasses import dataclass, field
from decimal import Decimal

from ..core.excecoes import Excecao, TipoExcecao
from ..core.ids import id_divergencia
from ..core.money import fmt, fmt_pct, round_money
from ..core.rastro import Rastro
from .checkout import LinhaCheckout

# Coluna extra `natureza` de divergencias_taxa.csv.
CONTRATO = "DIVERGENCIA_CONTRATO"
# ✅ Helena 10h58: condição comercial que a Orbe não conhecia (Casa). Fica listada, marcada, e não entra
# na cobrança da Orbe: vira devolução ao lojista.
ISENCAO = "ISENCAO_NAO_INFORMADA_ORBE"
_TAXA_DA_PLANILHA = ("PLANILHA", "R2")


@dataclass
class ResultadoDivergencias:
    divergencias: list[dict] = field(default_factory=list)
    excecoes: list[Excecao] = field(default_factory=list)


def _natureza(l: LinhaCheckout) -> str:
    """Se o contratado veio de um override (condição combinada fora da planilha), a Orbe cobrou certo pelo
    que sabia: não há o que cobrar dela. ⚠️ Premissa: todo override de taxa é condição não informada à Orbe."""
    return CONTRATO if l.taxa.regra_id in _TAXA_DA_PLANILHA else ISENCAO


def calcular_divergencias(linhas: list[LinhaCheckout], rastro: Rastro, mes: str,
                          nomes: dict[str, str] | None = None,
                          incluir_estornos: bool = True) -> ResultadoDivergencias:
    """✅ D1/D2: compara a TAXA (exata), nunca o valor em R$, o que elimina por construção os alarmes
    de R$ 0,01 da truncagem da Orbe. Valor = round(bruto × (aplicada − contratada)), por linha.

    `incluir_estornos` é o 🟡 V15: estorno feito a taxa diferente entra com sinal negativo (⚠️ D4), e a
    pendência fica pelo líquido (✅ "a venda e o estorno se anulam; cobro da Orbe só o que sobrou").
    ✅ Pendência: uma por contraparte e lojista, com as transações no rastro (Casa Barton 11h01).
    Atlas não chega aqui: sem contrato, o motor de checkout não gera linha para ela (⚠️ D5).
    """
    nomes = nomes or {}
    res = ResultadoDivergencias()
    grupos: dict[tuple[str, str], list[tuple[LinhaCheckout, Decimal]]] = collections.defaultdict(list)
    cobrado: dict[str, Decimal] = {}
    for l in sorted(linhas, key=lambda l: l.tx.id_transacao):
        aplicada, contratada = l.tx.taxa_aplicada_pct, l.taxa.pct
        if aplicada == contratada:
            continue
        if l.tx.tipo == "ESTORNO" and not incluir_estornos:
            continue
        diferenca = round_money(l.tx.valor_bruto * (aplicada - contratada) / 100)
        ref = l.tx.id_transacao
        id_saida = id_divergencia("CHECKOUT", ref)
        natureza = _natureza(l)
        res.divergencias.append({
            "id_saida": id_saida, "cnpj": l.cnpj14, "linha_negocio": "CHECKOUT", "ref_origem": ref,
            "taxa_contratada_pct": fmt_pct(contratada), "taxa_aplicada_pct": fmt_pct(aplicada),
            "diferenca_brl": diferenca, "natureza": natureza,
        })
        rastro.add(id_saida, l.tx.arquivo, ref, diferenca, l.componente, fmt_pct(contratada), "D1")
        grupos[(l.cnpj14, natureza)].append((l, diferenca))
        if natureza == ISENCAO:
            # ✅ Helena 12h50 e 15h55: a devolução é o que a Orbe descontou de fato (valor_taxa) menos a
            # comissão contratada; a diferença para a fórmula da divergência é o truncamento da Orbe.
            cobrado[l.tx.id_transacao] = l.tx.valor_taxa - l.comissao

    competencia = mes.replace("-", "")
    for (cnpj, natureza), itens in sorted(grupos.items()):
        liquido = sum((d for _, d in itens), Decimal("0"))
        a_mais = sum((d for _, d in itens if d > 0), Decimal("0"))
        a_menos = sum((d for _, d in itens if d < 0), Decimal("0"))
        nome = nomes.get(cnpj, cnpj)
        pares = sorted({f"{fmt_pct(l.tx.taxa_aplicada_pct)}% x {fmt_pct(l.taxa.pct)}%" for l, _ in itens})
        resumo = (f"{len(itens)} transação(ões) de {nome} em {mes[5:]}/{mes[:4]} (aplicada x contratada: "
                  f"{', '.join(pares)}). R$ {fmt(a_mais)} a mais, R$ {fmt(a_menos)} em estornos, líquido "
                  f"R$ {fmt(liquido)}. Detalhe por transação no rastro e em divergencias_taxa.csv.")
        if natureza == ISENCAO:
            tipo = TipoExcecao.DEVOLUCAO_LOJISTA
            motivo = (f"Condição comercial não informada à Orbe: {resumo} A Orbe cobrou pela planilha; não "
                      f"entra na cobrança à Orbe. Devolver ao lojista, com o comercial.")
        else:
            tipo = TipoExcecao.DIVERGENCIA_ORBE
            motivo = (f"Orbe aplicou taxa diferente da contratada: {resumo} Cobrar o líquido da Orbe e "
                      f"devolver ao lojista é decisão do financeiro.")
        valores = {l.tx.id_transacao: (cobrado[l.tx.id_transacao] if natureza == ISENCAO else d) for l, d in itens}
        if natureza == ISENCAO:
            devolver = sum(valores.values(), Decimal("0"))
            motivo = (motivo.replace(f"líquido R$ {fmt(liquido)}.",
                                     f"líquido pela fórmula R$ {fmt(liquido)}.")
                      + f" Valor da devolução = o que a Orbe descontou de fato (valor_taxa) menos a comissão "
                        f"contratada: R$ {fmt(devolver)}; a diferença para a fórmula é o truncamento da Orbe.")
            liquido = devolver
        exc = Excecao.nova(tipo, f"{cnpj}-{competencia}", liquido, motivo)
        res.excecoes.append(exc)
        for l, d in itens:
            rastro.add(exc.id_saida, l.tx.arquivo, l.tx.id_transacao, valores[l.tx.id_transacao], l.componente,
                       fmt_pct(l.taxa.pct), "D3")
    res.excecoes.sort(key=lambda e: e.id_saida)
    return res
