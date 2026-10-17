"""Ingestão do extrato do Banco Aurora (05a): CSV ';' UTF-8 com cabeçalho do banco antes das colunas.

ref_origem = linha física do arquivo (L9…), contando as linhas do cabeçalho do banco. A cadeia de saldos é
conferida linha a linha (invariante I-B1): se não fecha, a leitura falha em vez de seguir com dado errado.
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from ..core.ledger import Ledger
from ..core.money import fmt, parse_br
from .erros import LayoutError
from .extrato import Extrato, Lancamento
from .texto import norm_texto

ARQUIVO = "05a_extrato_banco_aurora_cc4471_set2026.csv"
_COLUNAS = {"data": "data", "lancamento": "descricao", "documento": "documento",
            "valor (r$)": "valor", "saldo (r$)": "saldo"}
OBRIGATORIAS = {"data": "Data", "descricao": "Lançamento", "valor": "Valor (R$)", "saldo": "Saldo (R$)"}


def _data(texto: str, onde: str) -> date:
    try:
        return datetime.strptime(texto.strip(), "%d/%m/%Y").date()
    except ValueError as exc:
        raise LayoutError(f"Aurora: {onde}: data inválida {texto!r}") from exc


def _valor(texto: str, onde: str) -> Decimal | None:
    if not texto.strip():
        return None
    try:
        return parse_br(texto)
    except ValueError as exc:
        raise LayoutError(f"Aurora: {onde}: valor inválido {texto!r}") from exc


def ler_aurora(path: Path, ledger: Ledger | None = None, arquivo: str = ARQUIVO) -> Extrato:
    texto = Path(path).read_bytes().decode("utf-8-sig")
    linhas = list(csv.reader(io.StringIO(texto), delimiter=";"))
    cab = next((i for i, l in enumerate(linhas) if l and norm_texto(l[0]) == "data"
                and any(norm_texto(c) == "lancamento" for c in l)), None)
    if cab is None:
        raise LayoutError("Aurora: cabeçalho de colunas (Data;Lançamento;…) não encontrado")
    cols = {_COLUNAS[norm_texto(c)]: j for j, c in enumerate(linhas[cab]) if norm_texto(c) in _COLUNAS}
    faltam = [rotulo for campo, rotulo in OBRIGATORIAS.items() if campo not in cols]
    if faltam:
        raise LayoutError(f"Aurora: colunas ausentes: {', '.join(faltam)}")

    def cel(linha: list[str], campo: str) -> str:
        j = cols.get(campo)
        return linha[j].strip() if j is not None and j < len(linha) else ""

    lancamentos: list[Lancamento] = []
    saldo_inicial: Decimal | None = None
    saldo_final: Decimal | None = None
    saldo: Decimal | None = None
    for i, linha in enumerate(linhas[cab + 1:], start=cab + 2):
        if not any(c.strip() for c in linha):
            continue
        ref = f"L{i}"
        desc, dia_txt = cel(linha, "descricao"), cel(linha, "data")
        valor, saldo_linha = _valor(cel(linha, "valor"), ref), _valor(cel(linha, "saldo"), ref)
        rotulo = norm_texto(desc)
        if rotulo == "saldo anterior":
            if saldo_linha is None or lancamentos:
                raise LayoutError(f"Aurora: {ref}: SALDO ANTERIOR sem saldo ou fora do início")
            saldo_inicial = saldo = saldo_linha
            if ledger is not None:
                ledger.ignorar("Aurora", "saldo anterior ou final", ref)
            continue
        if rotulo == "saldo final":
            saldo_final = saldo_linha
            if ledger is not None:
                ledger.ignorar("Aurora", "saldo anterior ou final", ref)
            continue
        if not dia_txt:
            # Só aviso de rodapé pode ser pulado: linha com valor e sem data parece lançamento.
            if valor is not None or saldo_linha is not None:
                raise LayoutError(f"Aurora: {ref} tem valor ou saldo mas não tem data")
            if ledger is not None:
                ledger.ignorar("Aurora", "rodapé ou linha sem dado", ref)
            continue
        if valor is None:
            raise LayoutError(f"Aurora: {ref} tem data mas não tem valor")
        if saldo_linha is not None:
            if saldo is not None and saldo + valor != saldo_linha:
                raise LayoutError(f"Aurora: cadeia de saldos não fecha em {ref}: R$ {fmt(saldo)} + "
                                  f"R$ {fmt(valor)} ≠ R$ {fmt(saldo_linha)}")
            saldo = saldo_linha
        elif saldo is not None:
            saldo += valor
        lancamentos.append(Lancamento("AURORA", ref, _data(dia_txt, ref), desc, valor, arquivo))
    if saldo_final is not None and saldo is not None and saldo_final != saldo:
        raise LayoutError(f"Aurora: SALDO FINAL R$ {fmt(saldo_final)} difere do último saldo R$ {fmt(saldo)}")
    return Extrato(lancamentos, saldo_inicial, saldo_final)
