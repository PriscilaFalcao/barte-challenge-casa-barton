from __future__ import annotations

from datetime import date


def no_mes(dia: date, mes: str) -> bool:
    """`mes` no formato AAAA-MM."""
    return dia.strftime("%Y-%m") == mes
