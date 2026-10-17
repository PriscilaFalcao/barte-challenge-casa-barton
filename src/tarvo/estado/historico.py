"""Histórico de fechamentos: o que um mês anterior deixou pendente e o fechamento seguinte pode recuperar.

✅ Helena 11h41: quando o comercial confirma a taxa de um lojista sem contrato (a Atlas), a taxa vale desde o
começo e o fechamento seguinte fatura o mês que ficou pendente. Para isso o fechamento precisa saber o que os
anteriores deixaram em aberto, sem depender de alguém lembrar.

Layout lido (o mesmo que a interface web grava em data/web/fechamentos/<id>/): uma pasta por fechamento, com
`dados/` (os arquivos enviados), `saida/` (as saídas e o execucao.log) e, na interface, um `state.json`.
O mês de cada pasta vem da 1ª linha do `execucao.log` ("fechamento AAAA-MM").

Regras:
- Só conta fechamento de mês anterior ao que está sendo fechado. Para cada mês, vale o fechamento marcado como
  "closed" (se houver); senão o mais recente. Assim uma execução de teste não vira fonte de recuperação.
- O que vira candidato: pendência SEM_CONTRATO (ref_origem = EC) e as linhas daquele EC no arquivo da Orbe do
  mês. Quem decide se entra é o cálculo: só entra se o EC já tem contrato (ver engines/checkout).
- Não faturar duas vezes: linha já recuperada por outro fechamento do histórico (regra_id terminado em
  "+RECUP" no rastro.csv) fica de fora.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from ..ingest.orbe import OrbeTx, ler_orbe, unir_orbe

MARCA_RECUPERADA = "+RECUP"


@dataclass(frozen=True)
class Fechamento:
    pasta: Path
    mes: str
    fechado: bool


def _mes_do_log(saida: Path) -> str | None:
    log = saida / "execucao.log"
    if not log.is_file():
        return None
    primeira = log.read_text(encoding="utf-8").split("\n", 1)[0].strip()
    return primeira.split(" ", 1)[1] if primeira.startswith("fechamento ") else None


def _csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def fechamentos_anteriores(historico: Path, mes: str) -> list[Fechamento]:
    """Um fechamento por mês anterior a `mes`, do mais antigo ao mais recente."""
    por_mes: dict[str, list[tuple[float, Fechamento]]] = {}
    if not historico.is_dir():
        return []
    for pasta in sorted(p for p in historico.iterdir() if p.is_dir()):
        saida = pasta / "saida"
        mes_pasta = _mes_do_log(saida)
        if mes_pasta is None or mes_pasta >= mes or not (saida / "pendencias.csv").is_file():
            continue
        fechado = False
        estado = pasta / "state.json"
        if estado.is_file():
            try:
                status = json.loads(estado.read_text(encoding="utf-8")).get("status")
            except (OSError, ValueError):
                continue
            if status not in ("completed", "closed"):
                continue
            fechado = status == "closed"
        por_mes.setdefault(mes_pasta, []).append(((saida / "execucao.log").stat().st_mtime,
                                                  Fechamento(pasta, mes_pasta, fechado)))
    escolhidos = []
    for m in sorted(por_mes):
        candidatos = por_mes[m]
        fechados = [c for c in candidatos if c[1].fechado]
        escolhidos.append(max(fechados or candidatos, key=lambda c: c[0])[1])
    return escolhidos


def _ja_recuperadas(historico: Path) -> set[str]:
    """id_transacao de linhas que algum fechamento do histórico já faturou como recuperação."""
    ids: set[str] = set()
    for pasta in historico.iterdir() if historico.is_dir() else []:
        rastro = pasta / "saida" / "rastro.csv"
        if rastro.is_file():
            ids |= {r["ref_origem"] for r in _csv(rastro) if r.get("regra_id", "").endswith(MARCA_RECUPERADA)}
    return ids


@dataclass(frozen=True)
class LeituraHistorico:
    linhas: list[OrbeTx]  # linhas da Orbe pendentes por falta de contrato, ainda não recuperadas
    meses: dict[str, frozenset[str]]  # EC -> meses a recuperar
    ecs_com_vendas: set[str] | None  # ECs com venda em algum mês anterior; None = não há histórico legível


def ler_historico(historico: Path | None, mes: str, padroes_orbe: tuple[str, ...]) -> LeituraHistorico:
    """Lê os fechamentos anteriores uma vez: o que recuperar e quem já vendeu antes (para o "lojista novo")."""
    if historico is None:
        return LeituraHistorico([], {}, None)
    historico = Path(historico)
    ja = _ja_recuperadas(historico)
    linhas: dict[str, OrbeTx] = {}
    meses: dict[str, set[str]] = {}
    com_vendas: set[str] = set()
    leu_algum = False
    for f in fechamentos_anteriores(historico, mes):
        arquivos = sorted({p for padrao in padroes_orbe for p in (f.pasta / "dados").glob(padrao)},
                          key=lambda p: p.name)
        if not arquivos:
            continue
        lidas = [ler_orbe(p, p.name) for p in arquivos]
        txs, _ = unir_orbe(lidas[0], lidas[1:])
        leu_algum = True
        com_vendas |= {t.cod_estabelecimento for t in txs
                       if t.tipo == "VENDA" and t.data_movimento.strftime("%Y-%m") < mes}
        ecs = {r["ref_origem"] for r in _csv(f.pasta / "saida" / "pendencias.csv") if r["tipo"] == "SEM_CONTRATO"}
        for t in txs:
            if (t.cod_estabelecimento in ecs and t.data_movimento.strftime("%Y-%m") == f.mes
                    and t.id_transacao not in ja):
                linhas.setdefault(t.id_transacao, t)
                meses.setdefault(t.cod_estabelecimento, set()).add(f.mes)
    return LeituraHistorico(sorted(linhas.values(), key=lambda t: t.id_transacao),
                            {ec: frozenset(m) for ec, m in meses.items()}, com_vendas if leu_algum else None)


def linhas_para_recuperar(historico: Path | None, mes: str, padroes_orbe: tuple[str, ...]
                          ) -> tuple[list[OrbeTx], dict[str, frozenset[str]]]:
    """(linhas da Orbe, EC -> meses) dos meses anteriores com pendência SEM_CONTRATO ainda não recuperada."""
    h = ler_historico(historico, mes, padroes_orbe)
    return h.linhas, h.meses
