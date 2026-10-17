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
    web = sub.add_parser("web", help="inicia a interface local")
    web.add_argument("--port", type=int, default=8000)
    a = ap.parse_args(argv)

    if a.cmd == "web":
        from .web import serve

        serve(a.port)
        return

    res = fechar(a.mes, a.dados, a.saida)
    def total(linha: str) -> Decimal:
        return sum((c["comissao_brl"] for c in res.comissoes if c["linha_negocio"] == linha), Decimal("0"))

    print(f"{a.mes}: comissão de checkout R$ {fmt(total('CHECKOUT'))}, remessa R$ {fmt(total('REMESSA'))}, "
          f"{len(res.notas)} nota(s), {len(res.divergencias)} divergência(s), {len(res.excecoes)} pendência(s). Saídas em {a.saida}/")
