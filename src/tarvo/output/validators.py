"""Invariantes de consolidação (PRD 7.9). Abortam antes de escrever qualquer saída."""
from __future__ import annotations

from decimal import Decimal

from ..core.money import fmt
from ..core.rastro import Rastro

# Coluna que carrega o número reportado em cada saída (as 5 que têm rastro).
COLUNA_VALOR = {
    "comissoes_por_lojista": "comissao_brl",
    "divergencias_taxa": "diferenca_brl",
    "notas_a_emitir": "valor_brl",
    "lancamentos_classificados": "valor",
    "pendencias": "valor_brl",
}


class ValidationError(Exception):
    def __init__(self, falhas: list[str]):
        self.falhas = falhas
        super().__init__("\n".join(falhas))


def validar_i_r1(saidas: dict[str, list[dict]], rastro: Rastro) -> None:
    """I-R1: sum(rastro.valor) por id_saida == número reportado, em Decimal exato."""
    falhas: list[str] = []
    ids_no_rastro = set(rastro.ids())
    for nome, coluna in COLUNA_VALOR.items():
        vistos: set[str] = set()
        for linha in saidas.get(nome, []):
            id_saida, reportado = linha["id_saida"], linha[coluna]
            if id_saida in vistos:
                falhas.append(f"I-R1 {nome}: id_saida duplicado {id_saida}")
                continue
            vistos.add(id_saida)
            if id_saida not in ids_no_rastro:
                falhas.append(f"I-R1 {nome}: {id_saida} não tem nenhuma linha de rastro")
            elif not isinstance(reportado, Decimal) or rastro.soma(id_saida) != reportado:
                falhas.append(
                    f"I-R1 {nome}: {id_saida} reportado={reportado} rastro={fmt(rastro.soma(id_saida))}"
                )
    if falhas:
        raise ValidationError(falhas)


def validar_i_d1(divergencias: list[dict]) -> None:
    """I-D1: nenhuma divergência de checkout com taxa aplicada igual à contratada."""
    falhas = [
        f"I-D1 {d['id_saida']}: ref {d['ref_origem']} com taxa aplicada == contratada ({d['taxa_aplicada_pct']})"
        for d in divergencias
        if Decimal(d["taxa_aplicada_pct"]) == Decimal(d["taxa_contratada_pct"])
    ]
    if falhas:
        raise ValidationError(falhas)


def validar_i_n1(notas: list[dict]) -> None:
    """I-N1: nenhuma nota com valor <= 0 (✅ N2)."""
    falhas = [f"I-N1 {n['id_saida']}: nota com valor {fmt(n['valor_brl'])} (deve ser > 0)"
              for n in notas if n["valor_brl"] <= 0]
    if falhas:
        raise ValidationError(falhas)
