"""Registro de lojistas: a chave CNPJ <-> EC <-> nome (H1). Nunca existe passo 'nome parecido' (P5)."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable, Literal

from ..ingest.taxas import ContratoLinha


def norm_nome(texto: str) -> str:
    """Caixa, acento, pontuação e espaço. Só isso: igualdade exata depois."""
    s = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


@dataclass(frozen=True)
class Lojista:
    cnpj14: str
    nome_canonico: str
    ecs: tuple[str, ...]
    status: Literal["ATIVO", "INATIVO"]


@dataclass(frozen=True)
class Resolucao:
    situacao: Literal["LOJISTA", "SEM_CONTRATO", "NAO_RESOLVIDO"]
    lojista: Lojista | None = None
    nome: str | None = None  # nome informado pela config quando SEM_CONTRATO


class Registro:
    def __init__(self, lojistas: dict[str, Lojista], por_ec: dict[str, str],
                 por_alias: dict[str, str], sem_contrato: dict[str, str]) -> None:
        self._lojistas = lojistas
        self._por_ec = por_ec
        self._por_alias = por_alias
        self._sem_contrato = sem_contrato

    @classmethod
    def construir(
        cls,
        contratos: Iterable[ContratoLinha],
        ecs_extra: dict[str, str],
        sem_contrato: dict[str, str],
        aliases: dict[str, str] | None = None,
    ) -> "Registro":
        nomes: dict[str, str] = {}
        inativos: dict[str, list[bool]] = {}
        por_ec: dict[str, str] = {}

        def liga_ec(ec: str, cnpj: str) -> None:
            if por_ec.setdefault(ec, cnpj) != cnpj:
                raise ValueError(f"EC {ec} ligado a dois CNPJs: {por_ec[ec]} e {cnpj}")

        for c in contratos:
            nomes.setdefault(c.cnpj14, c.lojista)
            inativos.setdefault(c.cnpj14, []).append(c.inativo)
            if c.ec_orbe:
                liga_ec(c.ec_orbe, c.cnpj14)
        for ec, cnpj in ecs_extra.items():
            if cnpj not in nomes:
                raise ValueError(f"EC extra {ec} aponta para CNPJ fora da planilha: {cnpj}")
            liga_ec(ec, cnpj)

        por_alias: dict[str, str] = {}

        def liga_alias(texto: str, cnpj: str) -> None:
            chave = norm_nome(texto)
            if por_alias.setdefault(chave, cnpj) != cnpj:
                raise ValueError(f"alias {chave!r} aponta para dois lojistas")

        for cnpj, nome in nomes.items():
            liga_alias(nome, cnpj)
        for texto, cnpj in (aliases or {}).items():
            if cnpj not in nomes:
                raise ValueError(f"alias {texto!r} aponta para CNPJ fora da planilha: {cnpj}")
            liga_alias(texto, cnpj)

        lojistas = {
            cnpj: Lojista(
                cnpj, nome, tuple(sorted(ec for ec, c in por_ec.items() if c == cnpj)),
                "INATIVO" if all(inativos[cnpj]) else "ATIVO",
            )
            for cnpj, nome in nomes.items()
        }
        return cls(lojistas, por_ec, por_alias, dict(sem_contrato))

    def por_cnpj(self, cnpj14: str) -> Lojista | None:
        return self._lojistas.get(cnpj14)

    def lojistas(self) -> list[Lojista]:
        return list(self._lojistas.values())

    def classificar(self, ec: str | None = None, cnpj: str | None = None, nome: str | None = None) -> Resolucao:
        """Ordem: EC, CNPJ, alias exato. Nada casou: NAO_RESOLVIDO."""
        if ec is not None:
            if ec in self._por_ec:
                return Resolucao("LOJISTA", self._lojistas[self._por_ec[ec]])
            if ec in self._sem_contrato:
                return Resolucao("SEM_CONTRATO", nome=self._sem_contrato[ec])
        if cnpj is not None and cnpj in self._lojistas:
            return Resolucao("LOJISTA", self._lojistas[cnpj])
        if nome is not None and norm_nome(nome) in self._por_alias:
            return Resolucao("LOJISTA", self._lojistas[self._por_alias[norm_nome(nome)]])
        return Resolucao("NAO_RESOLVIDO")
