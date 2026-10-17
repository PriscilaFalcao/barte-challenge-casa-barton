"""Rastro por construção (P4): cada cálculo emite suas linhas junto com o valor."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class LinhaRastro:
    id_saida: str
    arquivo_origem: str
    ref_origem: str
    valor: Decimal
    componente: str = ""
    taxa_usada_pct: str = ""
    regra_id: str = ""


class Rastro:
    def __init__(self) -> None:
        self._linhas: list[LinhaRastro] = []
        self._chaves: set[tuple[str, str, str, str]] = set()

    def add(
        self,
        id_saida: str,
        arquivo_origem: str,
        ref_origem: str,
        valor: Decimal,
        componente: str = "",
        taxa_usada_pct: str = "",
        regra_id: str = "",
    ) -> None:
        if not isinstance(valor, Decimal):
            raise TypeError("valor do rastro deve ser Decimal")
        chave = (id_saida, arquivo_origem, ref_origem, componente)
        if chave in self._chaves:
            raise ValueError(f"linha de rastro duplicada: {chave}")
        self._chaves.add(chave)
        self._linhas.append(
            LinhaRastro(id_saida, arquivo_origem, ref_origem, valor, componente, taxa_usada_pct, regra_id)
        )

    @classmethod
    def de(cls, linhas) -> "Rastro":
        r = cls()
        for l in linhas:
            r.add(l.id_saida, l.arquivo_origem, l.ref_origem, l.valor, l.componente, l.taxa_usada_pct, l.regra_id)
        return r

    def soma(self, id_saida: str) -> Decimal:
        return sum((l.valor for l in self._linhas if l.id_saida == id_saida), Decimal("0"))

    def ids(self) -> list[str]:
        return sorted({l.id_saida for l in self._linhas})

    def linhas(self) -> list[LinhaRastro]:
        return list(self._linhas)
