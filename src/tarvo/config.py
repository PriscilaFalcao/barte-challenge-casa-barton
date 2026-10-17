"""Defaults de fábrica (config/defaults.yaml) mais as regras promovidas por decisão humana (estado, B8).

`ler_yaml` devolve o dicionário bruto (usado também no fingerprint das etapas); `construir_config` monta o
Config tipado; `mesclar_promovidas` aplica as regras que uma pessoa promoveu pela fila de validação."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

import re

import yaml

from .core.excecoes import TipoExcecao
from .ingest.taxas import PRODUTOS

DEFAULTS_PATH = Path(__file__).resolve().parent.parent / "config" / "defaults.yaml"


@dataclass(frozen=True)
class OverrideTaxa:
    cnpj14: str
    produtos: tuple[str, ...]
    taxa_pct: Decimal
    inicio: date
    fim: date
    regra_id: str
    fonte: str


@dataclass(frozen=True)
class RegraLancamento:
    id: str
    banco: str
    padrao: re.Pattern
    conta: str
    sinal: str | None  # credito | debito | None
    status: str
    pendencia_tipo: TipoExcecao | None = None
    pendencia_motivo: str = ""


@dataclass(frozen=True)
class AlertaLancamento:
    mes: str
    banco: str
    ref: str
    data: date
    valor: Decimal
    tipo: TipoExcecao
    motivo: str


@dataclass(frozen=True)
class ConfigAgentes:
    rotas: dict[TipoExcecao, str] = field(default_factory=dict)  # tipo de exceção -> agente
    limiar: dict[str, Decimal] = field(default_factory=dict)  # agente -> confiança mínima para aplicar
    max_chamadas_llm: int = 60
    modelos: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Config:
    ecs_extra: dict[str, str] = field(default_factory=dict)
    sem_contrato: dict[str, str] = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict)
    overrides: tuple[OverrideTaxa, ...] = ()
    regras_lancamento: tuple[RegraLancamento, ...] = ()
    conta_provisoria: dict[str, str] = field(default_factory=dict)
    alertas_lancamento: tuple[AlertaLancamento, ...] = ()
    quem_decide: dict[TipoExcecao, str] = field(default_factory=dict)
    bloqueantes: frozenset[TipoExcecao] = frozenset()
    agentes: ConfigAgentes = field(default_factory=ConfigAgentes)


def _override(o: dict) -> OverrideTaxa:
    invalidos = [p for p in o["produtos"] if p not in PRODUTOS]
    if invalidos:
        raise ValueError(f"override {o.get('regra_id')}: produto desconhecido {invalidos}")
    return OverrideTaxa(
        cnpj14=str(o["cnpj"]).zfill(14), produtos=tuple(o["produtos"]), taxa_pct=Decimal(str(o["taxa_pct"])),
        inicio=o["inicio"], fim=o["fim"], regra_id=o["regra_id"], fonte=o["fonte"],
    )


_BANCOS = {"AURORA", "MERIDIANO"}


def _regra(r: dict) -> RegraLancamento:
    rid = r.get("id")
    if r.get("banco") not in _BANCOS or r.get("sinal") not in (None, "credito", "debito"):
        raise ValueError(f"regra de lançamento {rid}: banco ou sinal inválido")
    pend = r.get("pendencia") or {}
    return RegraLancamento(
        id=rid, banco=r["banco"], padrao=re.compile(r["padrao"]), conta=str(r["conta"]), sinal=r.get("sinal"),
        status=str(r.get("status", "")),
        pendencia_tipo=TipoExcecao(pend["tipo"]) if pend else None, pendencia_motivo=pend.get("motivo", ""),
    )


def _alerta(a: dict) -> AlertaLancamento:
    if a.get("banco") not in _BANCOS:
        raise ValueError(f"alerta de lançamento {a.get('ref')}: banco inválido")
    return AlertaLancamento(mes=str(a["mes"]), banco=a["banco"], ref=str(a["ref"]), data=a["data"],
                            valor=Decimal(str(a["valor"])), tipo=TipoExcecao(a["tipo"]), motivo=a["motivo"])


def _agentes(a: dict) -> ConfigAgentes:
    return ConfigAgentes(
        rotas={TipoExcecao(k): str(v) for k, v in (a.get("rotas") or {}).items()},
        limiar={str(k): Decimal(str(v)) for k, v in (a.get("limiar") or {}).items()},
        max_chamadas_llm=int(a.get("max_chamadas_llm", 60)),
        modelos={str(k): str(v) for k, v in (a.get("modelos") or {}).items()},
    )


def ler_yaml(path: Path = DEFAULTS_PATH) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def mesclar_promovidas(dados: dict, promovidas: list[dict]) -> dict:
    """Regra promovida por uma pessoa vale sobre o default. Padrão de descrição entra NA FRENTE das regras
    de fábrica (o que o humano ensinou é mais específico); EC novo entra em ecs_extra."""
    dados = {**dados}
    regras = [p["payload"] for p in promovidas if p["tipo"] == "PADRAO_CONTA"]
    if regras:
        dados["regras_lancamento"] = regras + list(dados.get("regras_lancamento") or [])
    ecs = {p["payload"]["ec"]: p["payload"]["cnpj"] for p in promovidas if p["tipo"] == "EC_LOJISTA"}
    if ecs:
        dados["ecs_extra"] = {**(dados.get("ecs_extra") or {}), **ecs}
    return dados


def construir_config(dados: dict) -> Config:
    return Config(
        ecs_extra={str(k): str(v) for k, v in (dados.get("ecs_extra") or {}).items()},
        sem_contrato={str(k): str(v) for k, v in (dados.get("sem_contrato") or {}).items()},
        aliases={str(k): str(v) for k, v in (dados.get("aliases") or {}).items()},
        overrides=tuple(_override(o) for o in dados.get("overrides_taxa") or []),
        regras_lancamento=tuple(_regra(r) for r in dados.get("regras_lancamento") or []),
        conta_provisoria={str(k): str(v) for k, v in (dados.get("conta_provisoria") or {}).items()},
        alertas_lancamento=tuple(_alerta(a) for a in dados.get("alertas_lancamento") or []),
        quem_decide={TipoExcecao(k): str(v) for k, v in (dados.get("quem_decide") or {}).items()},
        bloqueantes=frozenset(TipoExcecao(t) for t in dados.get("bloqueantes") or []),
        agentes=_agentes(dados.get("agentes") or {}),
    )


def carregar_defaults(path: Path = DEFAULTS_PATH) -> Config:
    return construir_config(ler_yaml(path))
