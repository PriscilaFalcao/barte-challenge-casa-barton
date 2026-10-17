"""Ingestão do plano de contas do ERP Fênix (04): Latin-1, ';'. Só ACEITA_LANCTO=S recebe lançamento."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path

from .erros import LayoutError
from .texto import norm_texto

ARQUIVO = "04_plano_de_contas_fenix_erp.csv"
OBRIGATORIAS = {"cod_conta": "COD_CONTA", "descricao": "DESCRICAO", "aceita_lancto": "ACEITA_LANCTO"}


@dataclass(frozen=True)
class Conta:
    codigo: str
    descricao: str
    analitica: bool  # ACEITA_LANCTO = S


def ler_plano_contas(path: Path) -> dict[str, Conta]:
    texto = Path(path).read_bytes().decode("latin-1")
    linhas = [l for l in csv.reader(io.StringIO(texto), delimiter=";")]
    if not linhas:
        raise LayoutError("Plano de contas: arquivo vazio")
    cab = {norm_texto(c): j for j, c in enumerate(linhas[0])}
    faltam = [rotulo for chave, rotulo in OBRIGATORIAS.items() if chave not in cab]
    if faltam:
        raise LayoutError(f"Plano de contas: colunas ausentes: {', '.join(faltam)}")
    contas: dict[str, Conta] = {}
    for i, linha in enumerate(linhas[1:], start=2):
        if not any(c.strip() for c in linha):
            continue
        codigo = linha[cab["cod_conta"]].strip()
        aceita = linha[cab["aceita_lancto"]].strip().upper()
        if not codigo or aceita not in ("S", "N"):
            raise LayoutError(f"Plano de contas: linha {i} sem código ou com ACEITA_LANCTO {aceita!r}")
        if codigo in contas:
            raise LayoutError(f"Plano de contas: conta {codigo} repetida (linha {i})")
        contas[codigo] = Conta(codigo, linha[cab["descricao"]].strip(), aceita == "S")
    return contas


def ler_planos(paths: list[Path]) -> dict[str, Conta]:
    """Mais de um export do plano no mês: as contas se somam; a mesma conta em dois arquivos é erro."""
    contas: dict[str, Conta] = {}
    for p in paths:
        for codigo, conta in ler_plano_contas(p).items():
            if codigo in contas:
                raise LayoutError(f"Plano de contas: conta {codigo} repetida entre arquivos ({p.name})")
            contas[codigo] = conta
    return contas
