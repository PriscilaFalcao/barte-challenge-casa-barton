"""Defaults de fábrica (config/defaults.yaml). Em operação, as regras vivem no banco (B8)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

import re

import yaml

from .core.excecoes import TipoExcecao
from .ingest.taxas import PRODUTOS

DEFAULTS_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "defaults.yaml"


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
class Config:
    ecs_extra: dict[str, str] = field(default_factory=dict)
    sem_contrato: dict[str, str] = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict)
    overrides: tuple[OverrideTaxa, ...] = ()
    regras_lancamento: tuple[RegraLancamento, ...] = ()
    conta_provisoria: dict[str, str] = field(default_factory=dict)
    alertas_lancamento: tuple[AlertaLancamento, ...] = ()


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


def carregar_defaults(path: Path = DEFAULTS_PATH) -> Config:
    dados = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return Config(
        ecs_extra={str(k): str(v) for k, v in (dados.get("ecs_extra") or {}).items()},
        sem_contrato={str(k): str(v) for k, v in (dados.get("sem_contrato") or {}).items()},
        aliases={str(k): str(v) for k, v in (dados.get("aliases") or {}).items()},
        overrides=tuple(_override(o) for o in dados.get("overrides_taxa") or []),
        regras_lancamento=tuple(_regra(r) for r in dados.get("regras_lancamento") or []),
        conta_provisoria={str(k): str(v) for k, v in (dados.get("conta_provisoria") or {}).items()},
        alertas_lancamento=tuple(_alerta(a) for a in dados.get("alertas_lancamento") or []),
    )
