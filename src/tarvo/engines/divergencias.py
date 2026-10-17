"""Motor de divergências de checkout (PRD 7.5): taxa aplicada pela Orbe contra taxa contratada."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from ..core.excecoes import Excecao, TipoExcecao
from ..core.ids import id_divergencia
from ..core.money import fmt, fmt_pct, round_money
from ..core.rastro import Rastro
from ..ingest.orbe import ARQUIVO as ARQUIVO_ORBE
from .checkout import LinhaCheckout


@dataclass
class ResultadoDivergencias:
    divergencias: list[dict] = field(default_factory=list)
    excecoes: list[Excecao] = field(default_factory=list)


def calcular_divergencias(linhas: list[LinhaCheckout], rastro: Rastro,
                          incluir_estornos: bool = True) -> ResultadoDivergencias:
    """✅ D1/D2: compara a TAXA (exata), nunca o valor em R$, o que elimina por construção os alarmes
    de R$ 0,01 da truncagem da Orbe. Valor = round(bruto × (aplicada − contratada)), por linha.

    `incluir_estornos` é o 🟡 V15: estorno feito a taxa diferente entra com sinal negativo (⚠️ D4).
    Atlas não chega aqui: sem contrato, o motor de checkout não gera linha para ela (⚠️ D5).
    """
    res = ResultadoDivergencias()
    for l in sorted(linhas, key=lambda l: l.tx.id_transacao):
        aplicada, contratada = l.tx.taxa_aplicada_pct, l.taxa.pct
        if aplicada == contratada:
            continue
        if l.tx.tipo == "ESTORNO" and not incluir_estornos:
            continue
        diferenca = round_money(l.tx.valor_bruto * (aplicada - contratada) / 100)
        ref = l.tx.id_transacao
        id_saida = id_divergencia("CHECKOUT", ref)
        res.divergencias.append({
            "id_saida": id_saida, "cnpj": l.cnpj14, "linha_negocio": "CHECKOUT", "ref_origem": ref,
            "taxa_contratada_pct": fmt_pct(contratada), "taxa_aplicada_pct": fmt_pct(aplicada),
            "diferenca_brl": diferenca,
        })
        rastro.add(id_saida, ARQUIVO_ORBE, ref, diferenca, l.componente, fmt_pct(contratada), "D1")
        exc = Excecao.nova(
            TipoExcecao.DIVERGENCIA_ORBE, ref, diferenca,
            f"Orbe aplicou {fmt_pct(aplicada)}% e o contrato diz {fmt_pct(contratada)}% "
            f"({l.produto}, {l.tx.tipo}, bruto R$ {fmt(l.tx.valor_bruto)}). Devolver ao lojista ou "
            f"cobrar a Orbe é decisão caso a caso.")
        res.excecoes.append(exc)
        rastro.add(exc.id_saida, ARQUIVO_ORBE, ref, diferenca, l.componente, fmt_pct(contratada), "D3")
    return res
