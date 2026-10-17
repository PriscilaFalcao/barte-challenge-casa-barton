"""Linha de comando (modo sem interface, PRD 9). Mesmo motor que a interface vai chamar.

    python -m tarvo fechar  --mes 2026-09 [--dados dados/] [--saida saida/] [--estado data/ | --sem-estado] [--historico pasta/]
    python -m tarvo fila    --mes 2026-09 [--todas]
    python -m tarvo decidir --mes 2026-09 --id PEN-... --por Financeiro --motivo "..." (--conta C [--padrao REGEX] | --ec EC --cnpj CNPJ | --nota TEXTO) [--escopo caso|regra]
    python -m tarvo regras  [--desativar ID]

O estado (fila, decisões, regras promovidas, eventos e checkpoints) fica em data/, ou em $TARVO_ESTADO.
"""
from __future__ import annotations

import argparse
import os
import re
from decimal import Decimal
from pathlib import Path

from .core.ids import norm_cnpj
from .core.money import fmt
from .estado.db import Estado
from .ingest.plano_contas import ler_planos
from .pipeline import ARQUIVOS, _arquivos, fechar


def _estado_padrao() -> Path:
    return Path(os.environ.get("TARVO_ESTADO", "data"))


def _cmd_fechar(a) -> None:
    estado = None if a.sem_estado else a.estado
    res = fechar(a.mes, a.dados, a.saida, estado, historico=a.historico)

    def total(linha: str) -> Decimal:
        return sum((c["comissao_brl"] for c in res.comissoes if c["linha_negocio"] == linha), Decimal("0"))

    print(f"{a.mes}: comissão de checkout R$ {fmt(total('CHECKOUT'))}, remessa R$ {fmt(total('REMESSA'))}, "
          f"{len(res.notas)} nota(s), {len(res.divergencias)} divergência(s), {len(res.excecoes)} pendência(s). "
          f"Saídas em {a.saida}/")
    if estado is not None:
        print("etapas: " + ", ".join(f"{e} ({s})" for e, s in res.etapas))
        ag = res.agentes
        if ag is not None and ag.chamadas:
            origens = {o: sum(c.origem == o for c in ag.chamadas) for o in ("cache", "api", "sem_ia", "erro", "limite")}
            print("agentes: " + ", ".join(f"{n} {o}" for o, n in origens.items() if n)
                  + f"; {sum(c.resultado == 'APLICADA' for c in ag.chamadas)} aplicada(s)")


def _cmd_fila(a) -> None:
    db = Estado(a.estado)
    itens = db.fila(a.mes, a.todas)
    if not itens:
        print(f"fila de {a.mes} vazia (rode `fechar` com estado antes)")
        return
    for i in itens:
        bloq = " BLOQUEANTE" if i["bloqueante"] == "S" else ""
        print(f"[{i['estado']}{bloq}] {i['id_saida']}  R$ {i['valor_brl']}  -> {i['quem_decide']}")
        print(f"    {i['motivo']}")
        if i["proposta"]:
            print(f"    IA: {i['proposta']}")
    db.fechar()


def _cmd_decidir(a) -> None:
    db = Estado(a.estado)
    item = db.item_fila(a.mes, a.id)
    if item is None:
        raise SystemExit(f"ERRO: {a.id} não está na fila de {a.mes}; rode `tarvo fila --mes {a.mes}`")
    if a.conta:
        plano = ler_planos(_arquivos(a.dados, ARQUIVOS["plano"]))
        if a.conta not in plano or not plano[a.conta].analitica:
            raise SystemExit(f"ERRO: conta {a.conta} não existe no plano ou não aceita lançamento")
        if not item["id_saida"].startswith("PEN-CLASSIFICACAO") and a.escopo == "caso" \
                and not re.match(r"^(L\d+|MRD\w+)$", item["ref_origem"]):
            raise SystemExit("ERRO: decisão de conta só vale para pendência de lançamento bancário")
        payload = {"ref_origem": item["ref_origem"], "conta": a.conta}
        dec = db.registrar_decisao(a.mes, a.id, "CONTA", payload, a.escopo, a.por, a.motivo)
        if a.escopo == "regra":
            if not a.padrao or not a.banco:
                raise SystemExit("ERRO: --escopo regra com --conta exige --padrao (regex) e --banco")
            re.compile(a.padrao)
            regra = {"id": f"HUM-{dec}", "banco": a.banco, "padrao": a.padrao, "conta": a.conta,
                     "status": f"✅ decisão de {a.por}: {a.motivo}"}
            rid = db.promover_regra("PADRAO_CONTA", regra, a.por, a.motivo, dec)
            print(f"regra {rid} promovida: {a.banco} /{a.padrao}/ -> {a.conta} (vale para os próximos fechamentos)")
    elif a.ec:
        payload = {"ec": a.ec, "cnpj": norm_cnpj(a.cnpj)}
        dec = db.registrar_decisao(a.mes, a.id, "EC_LOJISTA", payload, "regra", a.por, a.motivo)
        rid = db.promover_regra("EC_LOJISTA", payload, a.por, a.motivo, dec)
        print(f"regra {rid} promovida: EC {a.ec} -> CNPJ {payload['cnpj']}")
    else:
        db.registrar_decisao(a.mes, a.id, "NOTA", {"texto": a.nota}, "caso", a.por, a.motivo)
    db.fechar()
    print(f"decisão registrada para {a.id}. Rode `tarvo fechar --mes {a.mes}` para aplicar; só as etapas "
          f"afetadas são recalculadas.")


def _cmd_regras(a) -> None:
    db = Estado(a.estado)
    if a.desativar:
        db.desativar_regra(a.desativar)
        print(f"regra {a.desativar} desativada")
    for r in db.regras(so_ativas=False):
        print(f"{r['id']} [{'ativa' if r['ativa'] else 'inativa'}] {r['tipo']} {r['payload']} "
              f"({r['autor']}, {r['criada_em']}: {r['motivo']})")
    db.fechar()


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="tarvo")
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fechar", help="fecha o mês e escreve as saídas")
    f.add_argument("--mes", required=True, help="AAAA-MM, ex.: 2026-09")
    f.add_argument("--dados", type=Path, default=Path("dados"))
    f.add_argument("--saida", type=Path, default=Path("saida"))
    f.add_argument("--estado", type=Path, default=_estado_padrao())
    f.add_argument("--historico", type=Path, default=None,
                   help="pasta com os fechamentos anteriores (uma subpasta por mês, com dados/ e saida/); "
                        "recupera o que ficou pendente por falta de contrato")
    f.add_argument("--sem-estado", action="store_true", help="roda puro, sem checkpoint, fila nem decisões")

    fi = sub.add_parser("fila", help="lista a fila de validação do mês")
    fi.add_argument("--mes", required=True)
    fi.add_argument("--todas", action="store_true", help="inclui as já resolvidas")
    fi.add_argument("--estado", type=Path, default=_estado_padrao())

    d = sub.add_parser("decidir", help="registra a decisão de uma pessoa sobre um item da fila")
    d.add_argument("--mes", required=True)
    d.add_argument("--id", required=True, help="id_saida da pendência (PEN-...)")
    d.add_argument("--por", required=True, help="quem decide")
    d.add_argument("--motivo", required=True)
    grupo = d.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--conta", help="conta analítica para o lançamento")
    grupo.add_argument("--ec", help="EC da Orbe a ligar a um CNPJ do cadastro")
    grupo.add_argument("--nota", help="decisão sem efeito no cálculo (ex.: 'contestar com a Ponte')")
    d.add_argument("--cnpj", help="com --ec")
    d.add_argument("--escopo", choices=["caso", "regra"], default="caso")
    d.add_argument("--padrao", help="com --conta --escopo regra: regex sobre a descrição normalizada")
    d.add_argument("--banco", choices=["AURORA", "MERIDIANO"], help="com --escopo regra")
    d.add_argument("--dados", type=Path, default=Path("dados"))
    d.add_argument("--estado", type=Path, default=_estado_padrao())

    r = sub.add_parser("regras", help="lista as regras promovidas por decisão humana")
    r.add_argument("--desativar", type=int, help="id da regra a desativar (reverter)")
    r.add_argument("--estado", type=Path, default=_estado_padrao())

    web = sub.add_parser("web", help="inicia a interface local")
    web.add_argument("--port", type=int, default=8000)
    a = ap.parse_args(argv)

    if a.cmd == "web":
        from .web import serve

        serve(a.port)
        return
    if a.cmd == "fechar":
        _cmd_fechar(a)
        return
    if a.cmd == "fila":
        _cmd_fila(a)
        return
    if a.cmd == "decidir":
        _cmd_decidir(a)
        return
    if a.cmd == "regras":
        _cmd_regras(a)
        return

    ap.error("comando desconhecido")
