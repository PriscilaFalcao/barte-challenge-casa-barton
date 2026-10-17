"""Dinheiro em Decimal exato (P6). Nada de float."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CENTAVO = Decimal("0.01")


def D(valor: str | int | Decimal) -> Decimal:
    if isinstance(valor, float):
        raise TypeError("float não é permitido em cálculo monetário; use str ou Decimal")
    return Decimal(valor)


def round_money(valor: Decimal) -> Decimal:
    """Meio centavo para cima, simétrico no negativo (-0,005 -> -0,01)."""
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def parse_br(texto: str) -> Decimal:
    """'66.026,00' -> 66026.00; '1,49%' -> 1.49."""
    limpo = texto.strip().rstrip("%").strip().replace(".", "").replace(",", ".")
    try:
        return Decimal(limpo)
    except Exception as exc:
        raise ValueError(f"número pt-BR inválido: {texto!r}") from exc


def fmt(valor: Decimal) -> str:
    """Formato de saída: 2 casas, ponto decimal, sem '-0.00'."""
    r = round_money(valor)
    if r == 0:
        r = Decimal("0.00")
    return f"{r:.2f}"


def fmt_pct(valor: Decimal) -> str:
    """Taxa em pontos percentuais com no mínimo 2 casas ('2.1' -> '2.10')."""
    n = valor.normalize()
    if n.as_tuple().exponent > -2:
        n = n.quantize(CENTAVO)
    return f"{n:f}"
