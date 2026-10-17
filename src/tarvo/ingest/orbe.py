"""Ingestão do relatório da Orbe (01): uma linha por transação."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from ..core.money import parse_br
from .erros import LayoutError

ARQUIVO = "01_orbe_relatorio_comissoes_set2026.csv"

COLUNAS = [
    "id_transacao", "data_movimento", "cod_estabelecimento", "nome_estabelecimento",
    "tipo_lancamento", "modalidade", "qtd_parcelas", "bandeira", "valor_bruto",
    "taxa_aplicada_pct", "valor_taxa", "valor_liquido", "id_referencia", "data_venda_original",
]
TIPOS = {
    "VENDA": "VENDA",
    "ESTORNO": "ESTORNO",
    "ANTECIPACAO": "ANTECIPACAO",
    "REVERSAO ANTECIPACAO": "REVERSAO_ANTECIPACAO",
}


@dataclass(frozen=True)
class OrbeTx:
    id_transacao: str
    data_movimento: date
    cod_estabelecimento: str
    nome_estabelecimento: str
    tipo: str
    modalidade: str
    qtd_parcelas: int | None
    bandeira: str
    valor_bruto: Decimal
    taxa_aplicada_pct: Decimal
    valor_taxa: Decimal
    valor_liquido: Decimal
    id_referencia: str | None
    data_venda_original: date | None
    arquivo: str = ""  # arquivo de origem da linha (rastro); vazio = o relatório principal (ARQUIVO)

    def __post_init__(self) -> None:
        if not self.arquivo:
            object.__setattr__(self, "arquivo", ARQUIVO)

    @property
    def ref_origem(self) -> str:
        return self.id_transacao


@dataclass(frozen=True)
class Substituicao:
    """Duas linhas com o mesmo id_transacao em arquivos diferentes: `mantida` é a mais recente, `descartada` sai."""
    mantida: OrbeTx
    descartada: OrbeTx


def _data(texto: str) -> date:
    return datetime.strptime(texto.strip(), "%d/%m/%Y").date()


def _linha(r: dict[str, str], arquivo: str) -> OrbeTx:
    tipo_cru = r["tipo_lancamento"].strip().upper()
    if tipo_cru not in TIPOS:
        raise LayoutError(f"tipo_lancamento desconhecido: {tipo_cru!r}")
    parcelas = r["qtd_parcelas"].strip()
    original = r["data_venda_original"].strip()
    return OrbeTx(
        id_transacao=r["id_transacao"].strip(),
        data_movimento=_data(r["data_movimento"]),
        cod_estabelecimento=r["cod_estabelecimento"].strip(),
        nome_estabelecimento=r["nome_estabelecimento"].strip(),
        tipo=TIPOS[tipo_cru],
        modalidade=r["modalidade"].strip(),
        qtd_parcelas=int(parcelas) if parcelas else None,
        bandeira=r["bandeira"].strip(),
        valor_bruto=parse_br(r["valor_bruto"]),
        taxa_aplicada_pct=parse_br(r["taxa_aplicada_pct"]),
        valor_taxa=parse_br(r["valor_taxa"]),
        valor_liquido=parse_br(r["valor_liquido"]),
        id_referencia=r["id_referencia"].strip() or None,
        data_venda_original=_data(original) if original else None,
        arquivo=arquivo,
    )


def ler_orbe(path: Path, arquivo: str = "") -> list[OrbeTx]:
    """`arquivo` é o nome que vai para o rastro; sem ele, a linha é do relatório principal (ARQUIVO)."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        leitor = csv.DictReader(f, delimiter=";")
        faltando = [c for c in COLUNAS if c not in (leitor.fieldnames or [])]
        if faltando:
            raise LayoutError(f"Orbe: colunas ausentes: {', '.join(faltando)}")
        txs: list[OrbeTx] = []
        vistos: set[str] = set()
        for r in leitor:
            id_tx = (r["id_transacao"] or "?").strip()
            try:
                t = _linha(r, arquivo)
            except (ValueError, LayoutError) as exc:
                raise LayoutError(f"Orbe: linha {leitor.line_num}, transação {id_tx}: {exc}") from exc
            if t.id_transacao in vistos:
                raise LayoutError(f"Orbe: id_transacao duplicado: {t.id_transacao}")
            vistos.add(t.id_transacao)
            txs.append(t)
    return txs


def unir_orbe(principal: list[OrbeTx], ajustes: list[list[OrbeTx]]) -> tuple[list[OrbeTx], list[Substituicao]]:
    """Soma os arquivos de ajuste ao relatório principal, na ordem recebida (premissa H-ajustes).

    Mesmo id_transacao em dois arquivos: a linha mais recente permanece e a mais antiga sai. Mais recente é a de
    maior data_movimento; em empate, a do arquivo que veio depois (o ajuste vale sobre o relatório). Cada troca
    vira uma Substituicao, para a pendência e o rastro. Nada some em silêncio."""
    unidas: dict[str, OrbeTx] = {t.id_transacao: t for t in principal}
    trocas: list[Substituicao] = []
    for linhas in ajustes:
        for t in linhas:
            atual = unidas.get(t.id_transacao)
            if atual is None:
                unidas[t.id_transacao] = t
            elif t.data_movimento >= atual.data_movimento:
                unidas[t.id_transacao] = t
                trocas.append(Substituicao(mantida=t, descartada=atual))
            else:
                trocas.append(Substituicao(mantida=atual, descartada=t))
    return list(unidas.values()), trocas
