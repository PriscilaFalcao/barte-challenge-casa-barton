"""InterpreteTaxas (PRD 8.2): lê vigência em texto livre da planilha. Modelo: Sonnet 5.5.
Nunca aplica sozinho: a saída é proposta na fila, para o comercial confirmar (é regra de contrato)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from ..ingest.taxas import ContratoLinha
from .base import Agente


class InterpreteTaxas(Agente):
    nome = "interprete_taxas"
    max_tokens = 4096
    schema = {
        "type": "object",
        "properties": {
            "ambiguo": {"type": "boolean"},
            "vigencia_ini": {"type": "string"},
            "vigencia_fim": {"type": "string"},
            "confianca": {"type": "number"},
            "trecho_que_justifica": {"type": "string"},
            "pergunta": {"type": "string"},
        },
        "required": ["ambiguo", "vigencia_ini", "vigencia_fim", "confianca", "trecho_que_justifica", "pergunta"],
        "additionalProperties": False,
    }


def entrada(c: ContratoLinha, contratos: list[ContratoLinha]) -> dict:
    vizinhas = [{"ref": o.ref_origem, "vigencia_texto": o.vigencia_texto or "", "obs": o.obs or ""}
                for o in contratos if o.cnpj14 == c.cnpj14 and o.ref_origem != c.ref_origem]
    return {"lojista": c.lojista, "ref": c.ref_origem, "vigencia_texto": c.vigencia_texto or "", "obs": c.obs or "",
            "linhas_vizinhas": vizinhas}


def _data(texto: str) -> date | None:
    return date.fromisoformat(texto) if texto else None


def validar(saida: dict, ent: dict) -> tuple[dict | None, str]:
    """Guardrail: datas válidas e em ordem, e o trecho citado existe de fato no texto da planilha."""
    try:
        conf = Decimal(str(saida.get("confianca"))).quantize(Decimal("0.01"))
        ini, fim = _data(saida.get("vigencia_ini", "")), _data(saida.get("vigencia_fim", ""))
    except (InvalidOperation, ValueError, TypeError):
        return None, "data ou confiança inválida"
    if ini and fim and ini > fim:
        return None, "início depois do fim"
    trecho = str(saida.get("trecho_que_justifica", "")).strip()
    fonte = f"{ent['vigencia_texto']} {ent['obs']}"
    if not saida.get("ambiguo") and (not trecho or trecho not in fonte):
        return None, "trecho citado não está no texto da planilha"
    return {"ambiguo": bool(saida.get("ambiguo")), "ini": ini, "fim": fim, "confianca": conf, "trecho": trecho,
            "pergunta": str(saida.get("pergunta", "")).strip()}, ""


def texto_proposta(v: dict) -> str:
    if v["ambiguo"]:
        return f"IA: vigência ambígua. Pergunta sugerida: {v['pergunta']}"
    periodo = f"{v['ini'] or 'sem início'} a {v['fim'] or 'sem fim'}"
    return (f"IA propõe vigência {periodo} (confiança {v['confianca']}; trecho: \"{v['trecho']}\"). "
            f"Só vale depois de confirmada pelo comercial.")
