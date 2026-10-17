"""Inspeção manual do B1 (ingestão, registro de lojistas e resolvedor de taxa).

Uso (da raiz do repo):
  .venv/bin/python src/scripts/inspecionar_b1.py                       # resumo geral
  .venv/bin/python src/scripts/inspecionar_b1.py --ec 1075624862 --produto CREDITO_1X --data 2026-09-15
  .venv/bin/python src/scripts/inspecionar_b1.py --dados outra_pasta/  # outros arquivos, mesmo formato
"""
from __future__ import annotations

import argparse
import collections
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tarvo.config import carregar_defaults  # noqa: E402
from tarvo.contracts.resolver import ContratoError, Resolvedor, produto_de  # noqa: E402
from tarvo.core.money import fmt_pct  # noqa: E402
from tarvo.identity.registro import Registro  # noqa: E402
from tarvo.ingest.orbe import ler_orbe  # noqa: E402
from tarvo.ingest.taxas import PRODUTOS, ler_taxas  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dados", default="dados")
    ap.add_argument("--ec")
    ap.add_argument("--produto", choices=PRODUTOS)
    ap.add_argument("--data", type=date.fromisoformat)
    a = ap.parse_args()

    dados = Path(a.dados)
    cfg = carregar_defaults()
    contratos, excecoes = ler_taxas(next(dados.glob("02_*.xlsx")))
    reg = Registro.construir(contratos, cfg.ecs_extra, cfg.sem_contrato, cfg.aliases)
    rs = Resolvedor(contratos, cfg.overrides)
    txs = ler_orbe(next(dados.glob("01_*.csv")))

    if a.ec:
        res = reg.classificar(ec=a.ec)
        print(f"EC {a.ec}: {res.situacao}", res.lojista or res.nome or "")
        if res.lojista and a.produto and a.data:
            try:
                t = rs.taxa(res.lojista.cnpj14, a.produto, a.data)
                print(f"taxa {a.produto} em {a.data}: {fmt_pct(t.pct)}%  regra={t.regra_id}  origem={t.ref_origem}")
            except ContratoError as e:
                print(f"EXCEÇÃO {e.tipo.value}: {e.motivo}")
        return

    print(f"Planilha: {len(contratos)} linhas, {len(reg.lojistas())} lojistas, {len(excecoes)} exceções de leitura")
    for e in excecoes:
        print(f"  {e.tipo.value} {e.ref_origem}: {e.motivo}")
    print(f"Orbe: {len(txs)} transações")
    print("  por tipo:", dict(collections.Counter(t.tipo for t in txs)))
    sit = collections.Counter(reg.classificar(ec=t.cod_estabelecimento).situacao for t in txs)
    print("  por situação do EC:", dict(sit))
    nao = sorted({t.cod_estabelecimento for t in txs if reg.classificar(ec=t.cod_estabelecimento).situacao == "NAO_RESOLVIDO"})
    print("  ECs não resolvidos:", nao or "nenhum")

    difere = collections.Counter()
    for t in txs:
        loj = reg.classificar(ec=t.cod_estabelecimento).lojista
        if not loj:
            continue
        if t.tipo in ("ANTECIPACAO", "REVERSAO_ANTECIPACAO"):
            prod, dia = "ANTECIPACAO", t.data_movimento if t.tipo == "ANTECIPACAO" else t.data_venda_original
        else:
            try:
                prod = produto_de(t.modalidade, t.qtd_parcelas)
            except ContratoError:
                difere[(loj.nome_canonico, "FAIXA FORA DO CONTRATO")] += 1
                continue
            dia = t.data_movimento if t.tipo == "VENDA" else t.data_venda_original
        try:
            if rs.taxa(loj.cnpj14, prod, dia).pct != t.taxa_aplicada_pct:
                difere[(loj.nome_canonico, prod)] += 1
        except ContratoError:
            difere[(loj.nome_canonico, "SEM TAXA VIGENTE")] += 1
    print("Linhas com taxa aplicada ≠ contratada (lojista, produto: qtd):")
    for (nome, prod), n in sorted(difere.items()):
        print(f"  {nome}, {prod}: {n}")
    if not difere:
        print("  nenhuma")


if __name__ == "__main__":
    main()
