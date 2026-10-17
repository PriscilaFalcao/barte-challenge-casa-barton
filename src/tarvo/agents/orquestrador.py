"""Orquestrador (PRD 8.3, decisão A1): máquina de estados em código, não um LLM. Roteia cada exceção pelo tipo
para o agente da tabela `agentes.rotas`, valida a saída (guardrail + limiar) e decide entre aplicar, anexar
como proposta ou deixar com a pessoa. Não decide nada de negócio e não toca em valor em R$."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from ..config import Config
from ..core.excecoes import Excecao, TipoExcecao
from ..core.ids import id_lancamento
from ..core.rastro import LinhaRastro
from ..ingest.extrato import Lancamento
from ..ingest.orbe import OrbeTx
from ..ingest.plano_contas import Conta
from ..ingest.taxas import ContratoLinha
from . import classificador, interprete_taxas, investigador
from .base import CACHE_PADRAO, Agente, ClienteLLM

_CLASSES = {"classificador": classificador.Classificador, "interprete_taxas": interprete_taxas.InterpreteTaxas,
            "investigador": investigador.Investigador}


@dataclass(frozen=True)
class Chamada:
    agente: str
    id_saida: str
    hash: str
    origem: str  # cache | api | sem_ia | erro | limite
    resultado: str  # APLICADA | PROPOSTA | DESCARTADA | SEM_RESPOSTA
    detalhe: str = ""


@dataclass
class ResultadoAgentes:
    lancamentos: list[dict]
    excecoes: list[Excecao]
    enriquecimento: dict[str, dict] = field(default_factory=dict)  # id_saida -> colunas extras da pendência
    regra_lancamento: dict[str, str] = field(default_factory=dict)  # id_saida do lançamento -> regra_id novo
    chamadas: list[Chamada] = field(default_factory=list)
    chamadas_api: int = 0


@dataclass
class Contexto:
    """Tudo o que o código usa para montar a entrada dos agentes. Nada disso vai inteiro para o modelo."""
    plano: dict[str, Conta]
    lancamentos: list[Lancamento]
    txs: list[OrbeTx]
    contratos: list[ContratoLinha]
    rastro_por_id: dict[str, list[LinhaRastro]]


def orquestrar(excecoes: list[Excecao], lancamentos: list[dict], ctx: Contexto, cfg: Config,
               cliente: ClienteLLM | None, decididas: set[str], cache: Path = CACHE_PADRAO) -> ResultadoAgentes:
    ca = cfg.agentes
    agentes: dict[str, Agente] = {nome: cls(ca.modelos.get(nome, ""), cliente, cache)
                                  for nome, cls in _CLASSES.items() if nome in set(ca.rotas.values())}
    res = ResultadoAgentes(lancamentos=[dict(l) for l in lancamentos], excecoes=[])
    linhas_por_id = {l["id_saida"]: l for l in res.lancamentos}
    lan_por_ref = {(l.banco, l.ref_origem): l for l in ctx.lancamentos}
    contrato_por_ref = {c.ref_origem: c for c in ctx.contratos}

    for exc in sorted(excecoes, key=lambda e: e.id_saida):  # ordem fixa: mesmo teto de chamadas, mesmo resultado
        nome = ca.rotas.get(exc.tipo)
        if exc.id_saida in decididas or nome is None or nome not in agentes:
            res.excecoes.append(exc)  # já decidida por uma pessoa, ou tipo sem agente: fila humana
            continue
        agente = agentes[nome]
        pode = res.chamadas_api < ca.max_chamadas_llm

        if nome == "classificador":
            l = next((lan_por_ref[k] for k in lan_por_ref if k[1] == exc.ref_origem), None)
            if l is None:
                res.excecoes.append(exc)
                continue
            cands = classificador.candidatos(l, ctx.plano, cfg.conta_provisoria)
            ent = classificador.entrada(l, cands)
            r = agente.executar(ent, pode)
            res.chamadas_api += r.origem == "api"
            if r.saida is None:
                res.chamadas.append(Chamada(nome, exc.id_saida, r.hash, r.origem, "SEM_RESPOSTA", r.detalhe))
                res.excecoes.append(exc)
                continue
            v, erro = classificador.validar(r.saida, cands)
            limiar = ca.limiar.get(nome, Decimal("0.8"))
            if v is not None and v["confianca"] >= limiar:
                id_lan = id_lancamento(l.banco, l.ref_origem)
                linhas_por_id[id_lan].update(conta_codigo=v["conta_codigo"], metodo="IA", confianca=v["confianca"],
                                             regra_id="IA-CLASSIFICADOR")
                res.regra_lancamento[id_lan] = "IA-CLASSIFICADOR"
                res.chamadas.append(Chamada(nome, exc.id_saida, r.hash, r.origem, "APLICADA", v["justificativa"]))
                continue  # resolvida pelo agente: sai das pendências (PRD 7.7, passo 3)
            proposta = (f"IA sugere {v['conta_codigo']} com confiança {v['confianca']} (abaixo do limiar {limiar}): "
                        f"{v['justificativa']}" if v else f"IA: proposta descartada pelo guardrail ({erro}).")
            res.enriquecimento[exc.id_saida] = {"proposta_ia": proposta}
            res.chamadas.append(Chamada(nome, exc.id_saida, r.hash, r.origem, "PROPOSTA" if v else "DESCARTADA", erro))
            res.excecoes.append(exc)

        elif nome == "interprete_taxas":
            c = contrato_por_ref.get(exc.ref_origem)
            if c is None:  # CONTRATO_AMBIGUO que não veio da planilha (ex.: sem contrato vigente na data)
                res.excecoes.append(exc)
                continue
            ent = interprete_taxas.entrada(c, ctx.contratos)
            r = agente.executar(ent, pode)
            res.chamadas_api += r.origem == "api"
            res.excecoes.append(exc)  # nunca aplica sozinho: regra de contrato exige confirmação humana
            if r.saida is None:
                res.chamadas.append(Chamada(nome, exc.id_saida, r.hash, r.origem, "SEM_RESPOSTA", r.detalhe))
                continue
            v, erro = interprete_taxas.validar(r.saida, ent)
            res.enriquecimento[exc.id_saida] = {
                "proposta_ia": interprete_taxas.texto_proposta(v) if v else f"IA: proposta descartada ({erro})."}
            res.chamadas.append(Chamada(nome, exc.id_saida, r.hash, r.origem, "PROPOSTA" if v else "DESCARTADA", erro))

        else:  # investigador
            pend = {"tipo": exc.tipo.value, "ref_origem": exc.ref_origem, "valor_brl": exc.valor_brl,
                    "motivo": exc.motivo}
            ent = investigador.entrada(pend, ctx.rastro_por_id.get(exc.id_saida, []), ctx.lancamentos, ctx.txs)
            r = agente.executar(ent, pode)
            res.chamadas_api += r.origem == "api"
            res.excecoes.append(exc)  # não decide: só anexa hipóteses e pergunta
            if r.saida is None:
                res.chamadas.append(Chamada(nome, exc.id_saida, r.hash, r.origem, "SEM_RESPOSTA", r.detalhe))
                continue
            v, erro = investigador.validar(r.saida, ent)
            if v:
                res.enriquecimento[exc.id_saida] = {"hipoteses_ia": investigador.texto_hipoteses(v),
                                                    "pergunta_sugerida": v["pergunta"]}
            res.chamadas.append(Chamada(nome, exc.id_saida, r.hash, r.origem, "PROPOSTA" if v else "DESCARTADA", erro))
    return res
