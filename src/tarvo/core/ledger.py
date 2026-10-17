"""Registro de tudo o que o código descarta de propósito, para nada sumir em silêncio."""
from __future__ import annotations

import collections

AMOSTRA = 5


class Ledger:
    def __init__(self) -> None:
        self._itens: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
        self._contagem: collections.Counter[tuple[str, str]] = collections.Counter()

    def ignorar(self, fonte: str, motivo: str, ref: str | None = None) -> None:
        self._contagem[(fonte, motivo)] += 1
        if ref is not None:
            self._itens[(fonte, motivo)].append(ref)

    def contar(self, fonte: str, motivo: str) -> int:
        return self._contagem[(fonte, motivo)]

    def linhas_log(self) -> list[str]:
        saida = []
        for (fonte, motivo), n in sorted(self._contagem.items()):
            texto = f"{fonte}: {n} linha(s) ignorada(s) ({motivo})"
            refs = sorted(self._itens[(fonte, motivo)])[:AMOSTRA]
            saida.append(f"{texto}; ex.: {', '.join(refs)}" if refs else texto)
        return saida
