"""Ingestão do extrato do Banco Meridiano (05b): OFX 1.02 em SGML, CP1252, tags de valor sem fechamento.

Parser próprio por regex (ofxparse costuma falhar nesse formato). ref_origem = FITID.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .erros import LayoutError
from .extrato import Extrato, Lancamento

ARQUIVO = "05b_extrato_banco_meridiano_cc90233_set2026.ofx"
_TAG = re.compile(r"<([A-Z0-9.]+)>([^<\r\n]*)")


def _campos(bloco: str) -> dict[str, str]:
    campos: dict[str, str] = {}
    for tag, valor in _TAG.findall(bloco):
        campos.setdefault(tag, valor.strip())
    return campos


def _data(texto: str, onde: str) -> date:
    try:
        return datetime.strptime(texto[:8], "%Y%m%d").date()
    except ValueError as exc:
        raise LayoutError(f"Meridiano: {onde}: DTPOSTED inválido {texto!r}") from exc


def _dec(texto: str | None, onde: str) -> Decimal:
    try:
        return Decimal(texto or "")
    except InvalidOperation as exc:
        raise LayoutError(f"Meridiano: {onde}: valor inválido {texto!r}") from exc


def ler_meridiano(path: Path, arquivo: str = ARQUIVO) -> Extrato:
    texto = Path(path).read_bytes().decode("cp1252")
    if "<OFX>" not in texto.upper():
        raise LayoutError("Meridiano: arquivo não parece OFX (tag <OFX> ausente)")
    if "<BANKTRANLIST>" not in texto.upper():
        raise LayoutError("Meridiano: OFX sem <BANKTRANLIST>")
    lista = re.split(r"</BANKTRANLIST>", texto, flags=re.I)[0]
    # Cada transação vai de <STMTTRN> até </STMTTRN>, ou até a próxima <STMTTRN> se a tag não fechar.
    blocos = [re.split(r"</STMTTRN>", b, flags=re.I)[0] for b in re.split(r"<STMTTRN>", lista, flags=re.I)[1:]]

    lancamentos: list[Lancamento] = []
    vistos: set[str] = set()
    for n, bloco in enumerate(blocos, start=1):
        c = _campos(bloco)
        fitid = c.get("FITID", "")
        onde = f"transação {n} ({fitid or 'sem FITID'})"
        if not fitid:
            raise LayoutError(f"Meridiano: {onde}: FITID ausente")
        if fitid in vistos:
            raise LayoutError(f"Meridiano: FITID duplicado {fitid}")
        vistos.add(fitid)
        if "TRNAMT" not in c or "DTPOSTED" not in c:
            raise LayoutError(f"Meridiano: {onde}: TRNAMT ou DTPOSTED ausente")
        valor = _dec(c["TRNAMT"], onde)
        tipo = c.get("TRNTYPE", "").upper()
        if (tipo == "CREDIT" and valor < 0) or (tipo == "DEBIT" and valor > 0):
            raise LayoutError(f"Meridiano: {onde}: TRNTYPE {tipo} com valor {valor}")
        descricao = c.get("MEMO") or c.get("NAME") or ""
        lancamentos.append(Lancamento("MERIDIANO", fitid, _data(c["DTPOSTED"], onde), descricao, valor, arquivo))

    m = re.search(r"<LEDGERBAL>.*?<BALAMT>([^<\r\n]*)", texto, flags=re.S | re.I)
    return Extrato(lancamentos, None, _dec(m.group(1).strip(), "LEDGERBAL") if m else None)
