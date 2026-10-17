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
    DEVOLUCAO_LOJISTA = "DEVOLUCAO_LOJISTA"
    ALERTA_ANTECIPACAO = "ALERTA_ANTECIPACAO"
    LANCAMENTO_SEM_ORIGEM = "LANCAMENTO_SEM_ORIGEM"
    REPASSE_ATIPICO = "REPASSE_ATIPICO"
    DEVOLUCAO_PIX = "DEVOLUCAO_PIX"
    ENTIDADE_NAO_RESOLVIDA = "ENTIDADE_NAO_RESOLVIDA"
    CONTRATO_AMBIGUO = "CONTRATO_AMBIGUO"
    CLASSIFICACAO_BAIXA_CONFIANCA = "CLASSIFICACAO_BAIXA_CONFIANCA"
    CONFERIR_MES_SEGUINTE = "CONFERIR_MES_SEGUINTE"
    STATUS_PONTE_DESCONHECIDO = "STATUS_PONTE_DESCONHECIDO"
    LINHA_ORBE_SUBSTITUIDA = "LINHA_ORBE_SUBSTITUIDA"


HELENA = "Helena"
COMERCIAL = "Diego"  # ✅ Casa Barton 11h01: "cadastro e contrato quem decide é o comercial"
HELENA_E_COMERCIAL = "Helena e Diego"

# Tabela 7.8 do PRD (✅ 17/10: cadastro e contrato com o comercial; a Bia mantém a planilha, mas não decide).
QUEM_DECIDE_DEFAULT: dict[TipoExcecao, str] = {
    TipoExcecao.DIVERGENCIA_ORBE: HELENA,
    TipoExcecao.CONTESTACAO_PONTE: HELENA,
    TipoExcecao.COMISSAO_NAO_POSITIVA: HELENA,
    TipoExcecao.SEM_CONTRATO: COMERCIAL,
    TipoExcecao.DEVOLUCAO_LOJISTA: HELENA_E_COMERCIAL,  # ✅ "devolução ao lojista, pendência minha com o comercial"
    TipoExcecao.ALERTA_ANTECIPACAO: HELENA_E_COMERCIAL,  # ✅ "quem precisa saber sou eu e o comercial"
    TipoExcecao.LANCAMENTO_SEM_ORIGEM: HELENA,
    TipoExcecao.REPASSE_ATIPICO: HELENA,
    TipoExcecao.DEVOLUCAO_PIX: HELENA,
    TipoExcecao.ENTIDADE_NAO_RESOLVIDA: COMERCIAL,
    TipoExcecao.CONTRATO_AMBIGUO: COMERCIAL,
    TipoExcecao.CLASSIFICACAO_BAIXA_CONFIANCA: HELENA,
    TipoExcecao.CONFERIR_MES_SEGUINTE: HELENA,
    TipoExcecao.STATUS_PONTE_DESCONHECIDO: HELENA,
    TipoExcecao.LINHA_ORBE_SUBSTITUIDA: HELENA,  # ⚠️ Helena 13h34: correção com o mesmo id, "o critério é de vocês"; mostrar a ela
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
