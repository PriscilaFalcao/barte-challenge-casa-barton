"""Investigador (PRD 8.2): hipóteses sobre anomalias sem regra. Modelo: Sonnet 5.5.
O pacote de evidências é montado por código; o agente só pode citar refs que estão nele, e não produz valor."""
from __future__ import annotations

import re
from datetime import timedelta

from ..core.money import fmt
from ..core.rastro import LinhaRastro
from ..ingest.extrato import Lancamento
from ..ingest.orbe import OrbeTx
from ..ingest.texto import norm_texto
from .base import Agente

JANELA_DIAS = 15
MAX_EVIDENCIAS = 40
_PREFIXOS = r"^(pix enviado|pix recebido|pix receb|devolucao pix -|ted recebida|ted enviada|ted receb)\s+"
_PLAUSIBILIDADE = ["alta", "media", "baixa"]


class Investigador(Agente):
    nome = "investigador"
    max_tokens = 8192
    schema = {
        "type": "object",
        "properties": {
            "hipoteses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "descricao": {"type": "string"},
                        "evidencia_refs": {"type": "array", "items": {"type": "string"}},
                        "plausibilidade": {"type": "string", "enum": _PLAUSIBILIDADE},
                    },
                    "required": ["descricao", "evidencia_refs", "plausibilidade"],
                    "additionalProperties": False,
                },
            },
            "pergunta_sugerida": {"type": "string"},
            "quem_decide_sugerido": {"type": "string"},
        },
        "required": ["hipoteses", "pergunta_sugerida", "quem_decide_sugerido"],
        "additionalProperties": False,
    }


def _contraparte(descricao: str) -> str:
    """Primeira palavra do nome depois do prefixo da operação: 'PIX ENVIADO ATLAS IDIOMAS LTDA' -> 'atlas'."""
    resto = re.sub(_PREFIXOS, "", norm_texto(descricao))
    palavras = [p for p in re.split(r"[^a-z0-9]+", resto) if len(p) > 2]
    return palavras[0] if palavras else ""


def _ev_lan(l: Lancamento) -> dict:
    return {"ref": l.ref_origem, "fonte": l.banco, "data": l.data.isoformat(), "descricao": l.descricao,
            "valor": fmt(l.valor)}


def _ev_tx(t: OrbeTx) -> dict:
    return {"ref": t.id_transacao, "fonte": "ORBE", "data": t.data_movimento.isoformat(),
            "descricao": f"{t.tipo} {t.nome_estabelecimento} {t.modalidade or ''}".strip(), "valor": fmt(t.valor_bruto)}


def entrada(pendencia: dict, linhas: list[LinhaRastro], lancamentos: list[Lancamento], txs: list[OrbeTx]) -> dict:
    """Evidências: as linhas de origem da pendência e, na janela de datas, os movimentos da mesma contraparte
    nos dois bancos e na Orbe. Resumo da Orbe por tipo, para o agente ver a ordem de grandeza sem 1.900 linhas."""
    por_ref_lan = {l.ref_origem: l for l in lancamentos}
    por_ref_tx = {t.id_transacao: t for t in txs}
    origem_lan = [por_ref_lan[l.ref_origem] for l in linhas if l.ref_origem in por_ref_lan]
    origem_tx = [por_ref_tx[l.ref_origem] for l in linhas if l.ref_origem in por_ref_tx]

    datas = [l.data for l in origem_lan] + [t.data_movimento for t in origem_tx]
    nomes = {_contraparte(l.descricao) for l in origem_lan} | {_contraparte(f"x {t.nome_estabelecimento}") for t in origem_tx}
    nomes.discard("")
    evid = {e["ref"]: e for e in [_ev_lan(l) for l in origem_lan] + [_ev_tx(t) for t in origem_tx]}
    if datas and nomes:
        ini, fim = min(datas) - timedelta(days=JANELA_DIAS), max(datas) + timedelta(days=JANELA_DIAS)
        for l in sorted(lancamentos, key=lambda l: (l.data, l.ref_origem)):
            if ini <= l.data <= fim and _contraparte(l.descricao) in nomes:
                evid.setdefault(l.ref_origem, _ev_lan(l))
    relacionados = [t for t in txs if norm_texto(t.nome_estabelecimento).split(" ")[0] in nomes]
    resumo_orbe = {}
    for t in relacionados:
        r = resumo_orbe.setdefault(t.tipo, {"linhas": 0, "bruto": 0, "primeira": None, "ultima": None})
        r["linhas"] += 1
        r["bruto"] += t.valor_bruto
        r["primeira"] = min(filter(None, [r["primeira"], t.data_movimento.isoformat()]))
        r["ultima"] = max(filter(None, [r["ultima"], t.data_movimento.isoformat()]))
    for r in resumo_orbe.values():
        r["bruto"] = fmt(r["bruto"])
    evidencias = sorted(evid.values(), key=lambda e: (e["data"], e["ref"]))[:MAX_EVIDENCIAS]
    return {"pendencia": {"tipo": pendencia["tipo"], "ref_origem": pendencia["ref_origem"],
                          "valor_brl": fmt(pendencia["valor_brl"]), "motivo": pendencia["motivo"]},
            "evidencias": evidencias, "resumo_orbe_da_contraparte": dict(sorted(resumo_orbe.items()))}


def validar(saida: dict, ent: dict) -> tuple[dict | None, str]:
    """Guardrail: cada hipótese só cita refs que estão no pacote de evidências; hipótese com ref inventada cai."""
    refs = {e["ref"] for e in ent["evidencias"]}
    validas = [h for h in saida.get("hipoteses", [])
               if h.get("plausibilidade") in _PLAUSIBILIDADE and h.get("descricao", "").strip()
               and set(h.get("evidencia_refs", [])) <= refs]
    if not validas:
        return None, "nenhuma hipótese com evidência válida"
    return {"hipoteses": validas[:3], "pergunta": str(saida.get("pergunta_sugerida", "")).strip()}, ""


def texto_hipoteses(v: dict) -> str:
    return " ".join(f"{i}) {h['descricao'].strip()} [plausibilidade {h['plausibilidade']}"
                    f"{'; evidências: ' + ', '.join(h['evidencia_refs']) if h['evidencia_refs'] else ''}]"
                    for i, h in enumerate(v["hipoteses"], start=1))
