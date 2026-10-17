import csv
import subprocess
import sys
from collections import defaultdict
from decimal import Decimal as D
from pathlib import Path

import pytest

from tarvo.cli import main
from tarvo.ingest.erros import LayoutError

SRC = Path(__file__).resolve().parents[1]


def _ler(p):
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def test_fechar_writes_the_checkout_outputs_and_they_reconcile(dados, tmp_path):
    main(["fechar", "--mes", "2026-09", "--dados", str(dados), "--saida", str(tmp_path)])
    comissoes = _ler(tmp_path / "comissoes_por_lojista.csv")
    rastro = _ler(tmp_path / "rastro.csv")
    pendencias = _ler(tmp_path / "pendencias.csv")
    soma = defaultdict(D)
    for r in rastro:
        soma[r["id_saida"]] += D(r["valor"])
    assert len(comissoes) == 35  # 21 de checkout + 14 de remessa
    for c in comissoes:
        assert soma[c["id_saida"]] == D(c["comissao_brl"])
    por_tipo = defaultdict(list)
    for p in pendencias:
        por_tipo[p["tipo"]].append(p)
        assert soma[p["id_saida"]] == D(p["valor_brl"])
    assert {t: len(v) for t, v in por_tipo.items()} == {"SEM_CONTRATO": 1, "DIVERGENCIA_ORBE": 2, "CONTESTACAO_PONTE": 6,
                                                      "COMISSAO_NAO_POSITIVA": 1, "DEVOLUCAO_LOJISTA": 1,
                                                      "ALERTA_ANTECIPACAO": 1, "CONFERIR_MES_SEGUINTE": 3,
                                                      "LANCAMENTO_SEM_ORIGEM": 1, "DEVOLUCAO_PIX": 1,
                                                      "REPASSE_ATIPICO": 1}
    assert por_tipo["SEM_CONTRATO"][0]["quem_decide"] == "Diego"
    notas = _ler(tmp_path / "notas_a_emitir.csv")
    assert len(notas) == 21  # 20 de checkout (a Casa não emite) + 1 de remessa para a Ponte
    for n in notas:
        assert soma[n["id_saida"]] == D(n["valor_brl"]) > 0
    divergencias = _ler(tmp_path / "divergencias_taxa.csv")
    assert len(divergencias) == 233  # 210 de checkout + 23 da Mundo Aberto (spread negativo não é divergência, V4)
    for d in divergencias:
        assert soma[d["id_saida"]] == D(d["diferenca_brl"])
        assert d["taxa_aplicada_pct"] != d["taxa_contratada_pct"]
    assert sum(D(d["diferenca_brl"]) for d in divergencias if d["linha_negocio"] == "CHECKOUT") == D("16973.65")
    por_linha = defaultdict(D)
    for c in comissoes:
        por_linha[c["linha_negocio"]] += D(c["comissao_brl"])
    assert dict(por_linha) == {"CHECKOUT": D("203735.34"), "REMESSA": D("39543.45")}


def test_two_runs_produce_identical_files(dados, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for d in (a, b):
        main(["fechar", "--mes", "2026-09", "--dados", str(dados), "--saida", str(d)])
    for nome in ("comissoes_por_lojista.csv", "divergencias_taxa.csv", "notas_a_emitir.csv", "rastro.csv",
                 "pendencias.csv", "execucao.log"):
        assert (a / nome).read_bytes() == (b / nome).read_bytes()


def test_bad_input_fails_before_writing_anything(dados, tmp_path):
    ruim = tmp_path / "dados"
    ruim.mkdir()
    for f in dados.iterdir():
        (ruim / f.name).write_bytes(f.read_bytes())
    orbe = next(ruim.glob("01_*.csv"))
    orbe.write_text(orbe.read_text().replace("taxa_aplicada_pct", "taxa"), encoding="utf-8")
    saida = tmp_path / "saida"
    with pytest.raises(LayoutError, match="taxa_aplicada_pct"):
        main(["fechar", "--mes", "2026-09", "--dados", str(ruim), "--saida", str(saida)])
    assert not saida.exists() or not list(saida.iterdir())


def test_python_dash_m_entrypoint(dados, tmp_path):
    r = subprocess.run([sys.executable, "-m", "tarvo", "fechar", "--mes", "2026-09", "--dados", str(dados),
                        "--saida", str(tmp_path)], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "rastro.csv").exists()


def test_planilha_exception_becomes_pending_with_rastro_line(dados, tmp_path):
    import openpyxl

    ruim = tmp_path / "dados"
    ruim.mkdir()
    for f in dados.iterdir():
        (ruim / f.name).write_bytes(f.read_bytes())
    xlsx = next(ruim.glob("02_*.xlsx"))
    wb = openpyxl.load_workbook(xlsx)
    ws = wb["Taxas vigentes"]
    ws["K6"] = "depois do carnaval"  # Bridge, linha 6
    wb.save(xlsx)
    saida = tmp_path / "saida"
    main(["fechar", "--mes", "2026-09", "--dados", str(ruim), "--saida", str(saida)])
    pend = {p["ref_origem"]: p for p in _ler(saida / "pendencias.csv")}
    assert pend["Taxas!L6"]["tipo"] == "CONTRATO_AMBIGUO"
    ras = [r for r in _ler(saida / "rastro.csv") if r["id_saida"] == pend["Taxas!L6"]["id_saida"]]
    assert [(r["arquivo_origem"], r["ref_origem"], r["valor"]) for r in ras] == [
        ("02_tabela_taxas_contratadas.xlsx", "Taxas!L6", "0.00")]


def test_wrong_month_fails_instead_of_writing_empty_outputs(dados, tmp_path):
    saida = tmp_path / "saida"
    with pytest.raises(LayoutError, match="nenhuma linha.*2026-10"):
        main(["fechar", "--mes", "2026-10", "--dados", str(dados), "--saida", str(saida)])
    assert not saida.exists() or not list(saida.iterdir())


def test_month_check_warns_when_only_one_source_is_empty():
    from tarvo.pipeline import checar_mes_com_dados

    assert checar_mes_com_dados(10, 5, "2026-09") == []
    assert "Ponte" in checar_mes_com_dados(10, 0, "2026-09")[0]
    assert "Orbe" in checar_mes_com_dados(0, 5, "2026-09")[0]
    with pytest.raises(LayoutError, match="nenhuma linha.*2026-09"):
        checar_mes_com_dados(0, 0, "2026-09")


def test_execution_log_reports_counts_ignored_rows_and_validations(dados, tmp_path):
    main(["fechar", "--mes", "2026-09", "--dados", str(dados), "--saida", str(tmp_path)])
    log = (tmp_path / "execucao.log").read_text(encoding="utf-8")
    for esperado in (
        "fechamento 2026-09",
        "Orbe: 1957 linha(s), 1957 no mês, 0 fora do mês",
        "Ponte: 233 linha(s), 233 no mês, 0 fora do mês",
        "Ponte: 2 linha(s) ignorada(s) (rodapé ou linha sem dado)",
        "Taxas: 1 linha(s) ignorada(s) (rodapé ou linha sem dado)",
        "validação: I-R1, I-R2, I-R3, I-D1, I-N1, I-C1 ok",
        "comissoes_por_lojista: 35 linha(s)",
        "pendencias: 18 linha(s), 0 bloqueante(s)",
        "Meridiano: PIX recebidos de lojistas − TEDs à Ponte no mês = R$ 18240.00 (recursos para remessas ainda não liquidados)",
        "Aurora: 84 lançamento(s); cadeia de saldos fecha (R$ 612334.81 -> R$ -1920088.60)",
        "Aurora: 2 linha(s) ignorada(s) (saldo anterior ou final); ex.: L8, L94",
        "Meridiano: 21 TED(s) à Ponte conciliada(s) com Σ(Valor R$ + IOF) das operações do dia",
        "lancamentos_classificados: 184 linha(s), 184 por REGRA",
    ):
        assert esperado in log, esperado


def test_dash_m_prints_clean_error_and_exits_1_on_wrong_month(dados, tmp_path):
    r = subprocess.run([sys.executable, "-m", "tarvo", "fechar", "--mes", "2026-10", "--dados", str(dados),
                        "--saida", str(tmp_path / "s")], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 1
    assert "nenhuma linha" in r.stderr and "Traceback" not in r.stderr


def test_web_command_starts_the_web_server(monkeypatch):
    from tarvo import web

    started = []
    monkeypatch.setattr(web, "serve", started.append)

    main(["web", "--port", "8123"])

    assert started == [8123]


def test_fechar_writes_lancamentos_classificados_that_reconcile(dados, tmp_path):
    main(["fechar", "--mes", "2026-09", "--dados", str(dados), "--saida", str(tmp_path)])
    lan = _ler(tmp_path / "lancamentos_classificados.csv")
    soma = defaultdict(D)
    for r in _ler(tmp_path / "rastro.csv"):
        soma[r["id_saida"]] += D(r["valor"])
    assert len(lan) == 184 and {l["banco"] for l in lan} == {"AURORA", "MERIDIANO"}
    assert list(lan[0])[:9] == ["id_saida", "banco", "ref_origem", "data", "descricao", "valor", "conta_codigo",
                                "metodo", "confianca"]
    for l in lan:
        assert soma[l["id_saida"]] == D(l["valor"]) and l["data"].startswith("2026-09-")
