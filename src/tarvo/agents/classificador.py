"""Classificador (PRD 8.2): conta para um lançamento que nenhuma regra reconhece. Modelo: Haiku 4.5."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from ..ingest.extrato import Lancamento
from ..ingest.plano_contas import Conta
from ..ingest.texto import norm_texto
from .base import Agente

MAX_CANDIDATOS = 12
# Sem palavra em comum, a ordem segue a natureza provável pelo sinal: saída de dinheiro costuma ser despesa ou
# baixa de passivo; entrada costuma ser crédito a identificar, receita ou baixa de ativo.
_PRIORIDADE = {"debito": ("4", "2", "1"), "credito": ("1.1.09", "3", "2", "1")}
_RUIDO = {"de", "da", "do", "e", "a", "o", "s", "sa", "ltda", "lt", "pix", "ted", "enviado", "enviada", "recebido",
          "recebida", "receb", "pagto", "debito", "deb", "aut", "c", "cc"}


class Classificador(Agente):
    nome = "classificador"
    max_tokens = 512
    schema = {
        "type": "object",
        "properties": {
            "conta_codigo": {"type": "string"},
            "confianca": {"type": "number"},
            "justificativa": {"type": "string"},
        },
        "required": ["conta_codigo", "confianca", "justificativa"],
        "additionalProperties": False,
    }


def _palavras(texto: str) -> set[str]:
    return {p for p in re.split(r"[^a-z0-9]+", norm_texto(texto)) if len(p) > 2 and p not in _RUIDO}


def candidatos(l: Lancamento, plano: dict[str, Conta], provisorias: dict[str, str]) -> list[dict]:
    """Só contas analíticas, pré-filtradas pelo sinal e ordenadas pelas palavras em comum com a descrição e,
    no empate, pela natureza provável do sinal. A conta provisória do sinal sempre entra, para o agente poder
    dizer 'não sei'. Até 12 contas."""
    sinal = "credito" if l.valor > 0 else "debito"
    proibido = "4" if sinal == "credito" else "3"  # entrada de dinheiro não é despesa; saída não é receita
    analiticas = [c for c in plano.values() if c.analitica and not c.codigo.startswith(proibido)]
    palavras = _palavras(l.descricao)
    prioridade = _PRIORIDADE[sinal]

    def natureza(c: Conta) -> int:
        return next((i for i, p in enumerate(prioridade) if c.codigo.startswith(p)), len(prioridade))
    ordenadas = sorted(analiticas, key=lambda c: (-len(palavras & _palavras(c.descricao)), natureza(c), c.codigo))
    escolhidas = [c for c in ordenadas if c.codigo != provisorias[sinal]][:MAX_CANDIDATOS - 1]
    escolhidas.append(plano[provisorias[sinal]])
    return [{"codigo": c.codigo, "descricao": c.descricao} for c in sorted(escolhidas, key=lambda c: c.codigo)]


def entrada(l: Lancamento, cands: list[dict]) -> dict:
    return {"banco": l.banco, "data": l.data.isoformat(), "descricao": l.descricao, "valor": str(l.valor),
            "candidatos": cands}


def validar(saida: dict, cands: list[dict]) -> tuple[dict | None, str]:
    """Guardrail: a conta tem que estar na lista de candidatas e a confiança em [0, 1]."""
    codigos = {c["codigo"] for c in cands}
    if saida.get("conta_codigo") not in codigos:
        return None, f"conta {saida.get('conta_codigo')!r} fora das candidatas"
    try:
        conf = Decimal(str(saida.get("confianca"))).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError):
        return None, "confiança inválida"
    if not Decimal("0") <= conf <= Decimal("1"):
        return None, "confiança fora de [0, 1]"
    return {"conta_codigo": saida["conta_codigo"], "confianca": conf,
            "justificativa": str(saida.get("justificativa", "")).strip()}, ""
