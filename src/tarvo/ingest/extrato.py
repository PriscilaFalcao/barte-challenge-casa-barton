"""Modelo comum dos dois extratos bancários (Aurora CSV e Meridiano OFX)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Lancamento:
    banco: str  # AURORA | MERIDIANO
    ref_origem: str  # Aurora: linha física (L9); Meridiano: FITID
    data: date
    descricao: str
    valor: Decimal  # assinado: crédito > 0, débito < 0
    arquivo: str


@dataclass(frozen=True)
class Extrato:
    lancamentos: list[Lancamento]
    saldo_inicial: Decimal | None
    saldo_final: Decimal | None
