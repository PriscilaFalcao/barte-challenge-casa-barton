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


# Pendências que são alertas: pedem atenção de alguém e não mudam nenhum valor do fechamento. Continuam em
# pendencias.csv (o formato de saída não tem arquivo de alertas); a interface as destaca e conta à parte.
# Espelhado em ALERT_TYPES de web/app.js.
TIPOS_ALERTA = frozenset({TipoExcecao.ALERTA_ANTECIPACAO.value, TipoExcecao.REPASSE_ATIPICO.value})

# Quem decide é uma área, não uma pessoa: a estrutura do time pode mudar (nomes só nos comentários de origem).
FINANCEIRO = "Financeiro"
COMERCIAL = "Comercial"  # ✅ Casa Barton 11h01: "cadastro e contrato quem decide é o comercial"
FINANCEIRO_E_COMERCIAL = "Financeiro e Comercial"

# Tabela 7.8 do PRD (✅ 17/10: cadastro e contrato com o comercial; quem mantém a planilha não decide).
QUEM_DECIDE_DEFAULT: dict[TipoExcecao, str] = {
    TipoExcecao.DIVERGENCIA_ORBE: FINANCEIRO,
    TipoExcecao.CONTESTACAO_PONTE: FINANCEIRO,
    TipoExcecao.COMISSAO_NAO_POSITIVA: FINANCEIRO,
    TipoExcecao.SEM_CONTRATO: COMERCIAL,
    TipoExcecao.DEVOLUCAO_LOJISTA: FINANCEIRO_E_COMERCIAL,  # ✅ "devolução ao lojista, pendência minha com o comercial"
    TipoExcecao.ALERTA_ANTECIPACAO: FINANCEIRO_E_COMERCIAL,  # ✅ "quem precisa saber sou eu e o comercial"
    TipoExcecao.LANCAMENTO_SEM_ORIGEM: FINANCEIRO,
    TipoExcecao.REPASSE_ATIPICO: FINANCEIRO,
    TipoExcecao.DEVOLUCAO_PIX: FINANCEIRO,
    TipoExcecao.ENTIDADE_NAO_RESOLVIDA: COMERCIAL,
    TipoExcecao.CONTRATO_AMBIGUO: COMERCIAL,
    TipoExcecao.CLASSIFICACAO_BAIXA_CONFIANCA: FINANCEIRO,
    TipoExcecao.CONFERIR_MES_SEGUINTE: FINANCEIRO,
    TipoExcecao.STATUS_PONTE_DESCONHECIDO: FINANCEIRO,
    TipoExcecao.LINHA_ORBE_SUBSTITUIDA: FINANCEIRO,  # ⚠️ Helena 13h34: correção com o mesmo id, "o critério é de vocês"; mostrar a ela
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
