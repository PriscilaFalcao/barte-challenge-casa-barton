"""Defaults de fábrica (config/defaults.yaml). Em operação, as regras vivem no banco (B8)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

import yaml

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
class Config:
    ecs_extra: dict[str, str] = field(default_factory=dict)
    sem_contrato: dict[str, str] = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict)
    overrides: tuple[OverrideTaxa, ...] = ()


def _override(o: dict) -> OverrideTaxa:
    invalidos = [p for p in o["produtos"] if p not in PRODUTOS]
    if invalidos:
        raise ValueError(f"override {o.get('regra_id')}: produto desconhecido {invalidos}")
    return OverrideTaxa(
        cnpj14=str(o["cnpj"]).zfill(14), produtos=tuple(o["produtos"]), taxa_pct=Decimal(str(o["taxa_pct"])),
        inicio=o["inicio"], fim=o["fim"], regra_id=o["regra_id"], fonte=o["fonte"],
    )


def carregar_defaults(path: Path = DEFAULTS_PATH) -> Config:
    dados = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return Config(
        ecs_extra={str(k): str(v) for k, v in (dados.get("ecs_extra") or {}).items()},
        sem_contrato={str(k): str(v) for k, v in (dados.get("sem_contrato") or {}).items()},
        aliases={str(k): str(v) for k, v in (dados.get("aliases") or {}).items()},
        overrides=tuple(_override(o) for o in dados.get("overrides_taxa") or []),
    )
