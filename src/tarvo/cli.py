"""python -m tarvo fechar --mes 2026-09 --dados dados/ --saida saida/"""
from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path

from .core.money import fmt
from .pipeline import fechar


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="tarvo")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fechar", help="fecha o mês e escreve as saídas")
    f.add_argument("--mes", required=True, help="AAAA-MM, ex.: 2026-09")
    f.add_argument("--dados", type=Path, default=Path("dados"))
    f.add_argument("--saida", type=Path, default=Path("saida"))
    a = ap.parse_args(argv)

    res = fechar(a.mes, a.dados, a.saida)
    total = sum((c["comissao_brl"] for c in res.comissoes), Decimal("0"))
    print(f"{a.mes}: {len(res.comissoes)} lojistas, comissão de checkout R$ {fmt(total)}, "
          f"{len(res.divergencias)} divergência(s), {len(res.excecoes)} pendência(s). Saídas em {a.saida}/")
