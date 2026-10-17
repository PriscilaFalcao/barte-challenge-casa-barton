"""Resolvedor de taxa vigente por (lojista, produto, data da venda). Função pura, sem I/O."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from ..config import OverrideTaxa
from ..core.excecoes import TipoExcecao
from ..ingest.taxas import PRODUTOS, ContratoLinha

SPREAD_PADRAO_PCT = Decimal("1.5")  # ✅ R2: em branco ou "padrão" = 1,5% sobre a PTAX


class ContratoError(Exception):
    """Contrato ausente, ambíguo ou fora do que o resolvedor sabe. O motor vira pendência."""

    def __init__(self, motivo: str, tipo: TipoExcecao = TipoExcecao.CONTRATO_AMBIGUO) -> None:
        super().__init__(motivo)
        self.tipo = tipo
        self.motivo = motivo


@dataclass(frozen=True)
class TaxaResolvida:
    pct: Decimal  # pontos percentuais
    regra_id: str  # "PLANILHA", "R2" ou o id do override (ex.: C8)
    ref_origem: str  # linha da planilha ou fonte do override


def produto_de(modalidade: str, qtd_parcelas: int | None) -> str:
    """Faixas pelas colunas da planilha. 🟡 V11: 13x ou mais vira exceção."""
    if modalidade == "DEBITO":
        return "DEBITO"
    if modalidade == "PIX":
        return "PIX"
    if modalidade == "CREDITO A VISTA":
        return "CREDITO_1X"
    if modalidade == "CREDITO PARCELADO":
        if qtd_parcelas is not None and 2 <= qtd_parcelas <= 6:
            return "CREDITO_2_6X"
        if qtd_parcelas is not None and 7 <= qtd_parcelas <= 12:
            return "CREDITO_7_12X"
        raise ContratoError(f"crédito parcelado em {qtd_parcelas}x fora das faixas 2-6x e 7-12x")
    raise ContratoError(f"modalidade desconhecida: {modalidade!r}")


def _vale(ini: date | None, fim: date | None, dia: date) -> bool:
    return (ini is None or ini <= dia) and (fim is None or dia <= fim)


class Resolvedor:
    def __init__(self, contratos: Iterable[ContratoLinha], overrides: Iterable[OverrideTaxa] = ()) -> None:
        self._linhas = [c for c in contratos if c.vigencia_valida]
        self._overrides = list(overrides)

    def _linha_vigente(self, cnpj14: str, dia: date) -> ContratoLinha:
        candidatas = [c for c in self._linhas
                      if c.cnpj14 == cnpj14 and _vale(c.vigencia_ini, c.vigencia_fim, dia)]
        if not candidatas:
            raise ContratoError(f"{cnpj14}: nenhuma linha vigente da planilha em {dia.isoformat()}")
        if len(candidatas) > 1:
            refs = ", ".join(c.ref_origem for c in candidatas)
            raise ContratoError(f"{cnpj14}: mais de uma linha vigente em {dia.isoformat()} ({refs})")
        return candidatas[0]

    def taxa(self, cnpj14: str, produto: str, dia: date) -> TaxaResolvida:
        if produto not in PRODUTOS:
            raise ContratoError(f"produto desconhecido: {produto!r}")
        ovr = [o for o in self._overrides
               if o.cnpj14 == cnpj14 and produto in o.produtos and _vale(o.inicio, o.fim, dia)]
        if len(ovr) > 1:
            raise ContratoError(f"{cnpj14}: mais de um override de taxa vigente para {produto} em {dia.isoformat()}")
        if ovr:
            return TaxaResolvida(ovr[0].taxa_pct, ovr[0].regra_id, ovr[0].fonte)
        linha = self._linha_vigente(cnpj14, dia)
        pct = linha.taxas[produto]
        if pct is None:
            raise ContratoError(f"{cnpj14}: {produto} não contratado na linha {linha.ref_origem}")
        return TaxaResolvida(pct, "PLANILHA", linha.ref_origem)

    def spread(self, cnpj14: str, dia: date) -> TaxaResolvida:
        linha = self._linha_vigente(cnpj14, dia)
        if linha.spread_remessa is None:
            return TaxaResolvida(SPREAD_PADRAO_PCT, "R2", linha.ref_origem)
        return TaxaResolvida(linha.spread_remessa, "PLANILHA", linha.ref_origem)
