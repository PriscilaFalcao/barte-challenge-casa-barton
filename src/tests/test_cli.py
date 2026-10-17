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
    assert len(comissoes) == 21
    for c in comissoes:
        assert soma[c["id_saida"]] == D(c["comissao_brl"])
    assert [(p["tipo"], p["quem_decide"]) for p in pendencias] == [("SEM_CONTRATO", "Diego")]
    assert soma[pendencias[0]["id_saida"]] == D(pendencias[0]["valor_brl"])
    assert sum(D(c["comissao_brl"]) for c in comissoes) == D("207039.73")


def test_two_runs_produce_identical_files(dados, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for d in (a, b):
        main(["fechar", "--mes", "2026-09", "--dados", str(dados), "--saida", str(d)])
    for nome in ("comissoes_por_lojista.csv", "rastro.csv", "pendencias.csv"):
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
