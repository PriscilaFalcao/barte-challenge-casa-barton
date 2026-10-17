"""Exceções dos motores: viram linhas de pendencias.csv ou cartões na fila humana."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from .ids import id_pendencia


class TipoExcecao(str, Enum):
    DIVERGENCIA_ORBE = "DIVERGENCIA_ORBE"
    CONTESTACAO_PONTE = "CONTESTACAO_PONTE"
    COMISSAO_NAO_POSITIVA = "COMISSAO_NAO_POSITIVA"
    SEM_CONTRATO = "SEM_CONTRATO"
    CASA_DEVOLUCAO = "CASA_DEVOLUCAO"
    LANCAMENTO_SEM_ORIGEM = "LANCAMENTO_SEM_ORIGEM"
    REPASSE_ATIPICO = "REPASSE_ATIPICO"
    DEVOLUCAO_PIX = "DEVOLUCAO_PIX"
    ENTIDADE_NAO_RESOLVIDA = "ENTIDADE_NAO_RESOLVIDA"
    CONTRATO_AMBIGUO = "CONTRATO_AMBIGUO"
    CLASSIFICACAO_BAIXA_CONFIANCA = "CLASSIFICACAO_BAIXA_CONFIANCA"
    CONFERIR_OUTUBRO = "CONFERIR_OUTUBRO"


# Tabela 7.8 do PRD. 🟡 V6: Diego em SEM_CONTRATO e Bia em CONTRATO_AMBIGUO ainda são premissas.
QUEM_DECIDE_DEFAULT: dict[TipoExcecao, str] = {
    TipoExcecao.DIVERGENCIA_ORBE: "Helena",
    TipoExcecao.CONTESTACAO_PONTE: "Helena",
    TipoExcecao.COMISSAO_NAO_POSITIVA: "Helena",
    TipoExcecao.SEM_CONTRATO: "Diego",
    TipoExcecao.CASA_DEVOLUCAO: "Helena",
    TipoExcecao.LANCAMENTO_SEM_ORIGEM: "Helena",
    TipoExcecao.REPASSE_ATIPICO: "Helena",
    TipoExcecao.DEVOLUCAO_PIX: "Helena",
    TipoExcecao.ENTIDADE_NAO_RESOLVIDA: "Helena",
    TipoExcecao.CONTRATO_AMBIGUO: "Helena",
    TipoExcecao.CLASSIFICACAO_BAIXA_CONFIANCA: "Helena",
    TipoExcecao.CONFERIR_OUTUBRO: "Helena",
}


@dataclass(frozen=True)
class Excecao:
    tipo: TipoExcecao
    ref_origem: str
    valor_brl: Decimal
    motivo: str
    quem_decide: str

    @property
    def id_saida(self) -> str:
        return id_pendencia(self.tipo.value, self.ref_origem)

    @classmethod
    def nova(
        cls,
        tipo: TipoExcecao,
        ref_origem: str,
        valor_brl: Decimal,
        motivo: str,
        quem_decide: str | None = None,
    ) -> "Excecao":
        if not motivo.strip():
            raise ValueError("exceção sem motivo")
        return cls(tipo, ref_origem, valor_brl, motivo, quem_decide or QUEM_DECIDE_DEFAULT[tipo])
