"""Escrita das 6 CSVs no formato fixo: ';', '.' decimal, AAAA-MM-DD, CNPJ com 14 dígitos."""
from __future__ import annotations

import csv
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from ..core.money import fmt
from ..core.rastro import Rastro

SCHEMAS: dict[str, list[str]] = {
    "comissoes_por_lojista": ["id_saida", "cnpj", "lojista", "linha_negocio", "comissao_brl"],
    "divergencias_taxa": ["id_saida", "cnpj", "linha_negocio", "ref_origem",
                          "taxa_contratada_pct", "taxa_aplicada_pct", "diferenca_brl"],
    "notas_a_emitir": ["id_saida", "tomador_cnpj", "tomador", "linha_negocio", "valor_brl", "discriminacao"],
    "lancamentos_classificados": ["id_saida", "banco", "ref_origem", "data", "descricao",
                                  "valor", "conta_codigo", "metodo", "confianca"],
    "pendencias": ["id_saida", "tipo", "ref_origem", "valor_brl", "motivo", "quem_decide"],
    "rastro": ["id_saida", "arquivo_origem", "ref_origem", "valor"],
}
RASTRO_EXTRAS = ["componente", "taxa_usada_pct", "regra_id"]

ENUMS = {
    "linha_negocio": {"CHECKOUT", "REMESSA"},
    "banco": {"AURORA", "MERIDIANO"},
    "metodo": {"REGRA", "IA", "HUMANO"},
}
CAMPOS_CNPJ = {"cnpj", "tomador_cnpj"}
_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _celula(valor) -> str:
    if isinstance(valor, Decimal):
        return fmt(valor)
    if isinstance(valor, date):
        return valor.isoformat()
    return "" if valor is None else str(valor)


def _validar_linha(nome: str, linha: dict, i: int) -> None:
    for col in SCHEMAS[nome]:
        if col not in linha:
            raise ValueError(f"{nome}: linha {i} sem a coluna obrigatória {col}")
    for col, validos in ENUMS.items():
        if col in linha and linha[col] not in validos:
            raise ValueError(f"{nome}: linha {i}, {col}={linha[col]!r} fora de {sorted(validos)}")
    for col in CAMPOS_CNPJ & linha.keys():
        if not re.fullmatch(r"\d{14}", str(linha[col])):
            raise ValueError(f"{nome}: linha {i}, {col}={linha[col]!r} não tem 14 dígitos")
    if "data" in linha and not _DATA.match(_celula(linha["data"])):
        raise ValueError(f"{nome}: linha {i}, data={linha['data']!r} fora de AAAA-MM-DD")
    if "confianca" in linha and not (Decimal("0") <= Decimal(str(linha["confianca"])) <= Decimal("1")):
        raise ValueError(f"{nome}: linha {i}, confianca={linha['confianca']!r} fora de [0,1]")


def _gravar(path: Path, colunas: list[str], linhas: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        w.writerow(colunas)
        for linha in linhas:
            w.writerow([_celula(linha.get(c)) for c in colunas])


def _ordenar(linhas: list[dict]) -> list[dict]:
    return sorted(linhas, key=lambda l: tuple(_celula(v) for v in l.values()))


def escrever_csv(path: Path, nome: str, linhas: list[dict]) -> None:
    for i, linha in enumerate(linhas, start=1):
        _validar_linha(nome, linha, i)
    extras = sorted({c for l in linhas for c in l} - set(SCHEMAS[nome]))
    _gravar(Path(path), SCHEMAS[nome] + extras, _ordenar(linhas))


def escrever_rastro(path: Path, rastro: Rastro) -> None:
    linhas = [
        {"id_saida": l.id_saida, "arquivo_origem": l.arquivo_origem, "ref_origem": l.ref_origem,
         "valor": l.valor, "componente": l.componente, "taxa_usada_pct": l.taxa_usada_pct,
         "regra_id": l.regra_id}
        for l in rastro.linhas()
    ]
    _gravar(Path(path), SCHEMAS["rastro"] + RASTRO_EXTRAS,
            sorted(linhas, key=lambda l: (l["id_saida"], l["ref_origem"], l["componente"])))
