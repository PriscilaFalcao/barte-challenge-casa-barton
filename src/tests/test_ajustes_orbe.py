"""Ajustes tardios da Orbe (06_*.csv): opcionais, mesmo formato do 01, a linha mais recente permanece."""
import csv
import shutil
from datetime import date
from decimal import Decimal

from tarvo.ingest.orbe import ARQUIVO, OrbeTx, ler_orbe, unir_orbe
from tarvo.pipeline import fechar

AJUSTES = "06_orbe_ajustes_tardios_set2026.csv"


def _tx(id_, dia, arquivo="", bruto="100.00"):
    return OrbeTx(id_, date(2026, 9, dia), "1", "N", "VENDA", "PIX", 1, "", Decimal(bruto), Decimal("1"),
                  Decimal("1.00"), Decimal("99.00"), None, None, arquivo)


def _ler(pasta):
    with open(pasta / "saida" / "rastro.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _fechar(dados, destino, com_ajustes):
    destino.mkdir()
    for p in dados.glob("0[1-5]*"):
        shutil.copy(p, destino / p.name)
    if com_ajustes:
        shutil.copy(dados / AJUSTES, destino / AJUSTES)
    return fechar("2026-09", destino, destino / "saida", cliente=None)


def test_linha_sem_arquivo_e_do_relatorio_principal():
    assert _tx("A", 1).arquivo == ARQUIVO


def test_ler_orbe_marca_o_arquivo_de_origem(dados):
    txs = ler_orbe(dados / AJUSTES, AJUSTES)
    assert len(txs) == 14 and {t.arquivo for t in txs} == {AJUSTES}


def test_id_novo_so_soma():
    unidas, trocas = unir_orbe([_tx("A", 1)], [[_tx("B", 30, "06")]])
    assert {t.id_transacao for t in unidas} == {"A", "B"} and trocas == []


def test_mesmo_id_a_mais_recente_permanece():
    unidas, trocas = unir_orbe([_tx("A", 10)], [[_tx("A", 30, "06", "200.00")]])
    (t,) = unidas
    assert t.arquivo == "06" and t.valor_bruto == Decimal("200.00")
    assert trocas[0].descartada.arquivo == ARQUIVO


def test_mesmo_id_com_data_anterior_no_ajuste_nao_substitui():
    unidas, trocas = unir_orbe([_tx("A", 30)], [[_tx("A", 10, "06")]])
    assert unidas[0].arquivo == ARQUIVO and trocas[0].descartada.arquivo == "06"


def test_empate_de_data_vale_o_arquivo_que_veio_depois():
    unidas, _ = unir_orbe([_tx("A", 30)], [[_tx("A", 30, "06")], [_tx("A", 30, "07")]])
    assert unidas[0].arquivo == "07"


def test_fechamento_inclui_o_06_e_aponta_o_arquivo_no_rastro(dados, tmp_path):
    sem = _fechar(dados, tmp_path / "sem", False)
    com = _fechar(dados, tmp_path / "com", True)
    assert sum(c["comissao_brl"] for c in com.comissoes) == sum(c["comissao_brl"] for c in sem.comissoes) \
        - Decimal("3304.39")
    assert len(com.divergencias) == len(sem.divergencias) and len(com.excecoes) == len(sem.excecoes)
    origens = {r["arquivo_origem"] for r in _ler(tmp_path / "com")}
    assert AJUSTES in origens and AJUSTES not in {r["arquivo_origem"] for r in _ler(tmp_path / "sem")}
    assert "Orbe: 2 arquivo(s) somados" in (tmp_path / "com" / "saida" / "execucao.log").read_text(encoding="utf-8")


def test_id_repetido_entre_arquivos_vira_pendencia_e_a_mais_recente_vale(dados, tmp_path):
    pasta = tmp_path / "dup"
    pasta.mkdir()
    for p in dados.glob("0[1-5]*"):
        shutil.copy(p, pasta / p.name)
    original = next(csv.DictReader(open(dados / "01_orbe_relatorio_comissoes_set2026.csv", encoding="utf-8-sig"),
                                   delimiter=";"))
    cab = open(dados / AJUSTES, encoding="utf-8").readline()
    linha = ";".join(original.values()).replace(original["data_movimento"], "30/09/2026")
    (pasta / AJUSTES).write_text(cab + linha + "\n", encoding="utf-8")
    res = fechar("2026-09", pasta, pasta / "saida", cliente=None)
    (p,) = [e for e in res.excecoes if e.tipo.value == "LINHA_ORBE_SUBSTITUIDA"]
    assert p.ref_origem == original["id_transacao"] and "mais recente permanece" in p.motivo
    ids = [r for r in _ler(pasta) if r["ref_origem"] == original["id_transacao"]]
    assert {r["arquivo_origem"] for r in ids} <= {ARQUIVO, AJUSTES}


def _pasta(dados, destino):
    destino.mkdir()
    for p in dados.glob("0[1-5]*"):
        shutil.copy(p, destino / p.name)
    return destino


def test_ponte_em_dois_arquivos_conta_cada_operacao_uma_vez(dados, tmp_path):
    base = fechar("2026-09", _pasta(dados, tmp_path / "a"), tmp_path / "a" / "saida", cliente=None)
    pasta = _pasta(dados, tmp_path / "b")
    shutil.copy(pasta / "03_email_ponte_cambio_relatorio_set2026.eml", pasta / "03_reenvio.eml")
    dup = fechar("2026-09", pasta, pasta / "saida", cliente=None)
    soma = lambda r: sum(c["comissao_brl"] for c in r.comissoes if c["linha_negocio"] == "REMESSA")
    assert soma(dup) == soma(base) == Decimal("39543.45")
    assert "Ponte: 2 arquivos somados" in (pasta / "saida" / "execucao.log").read_text(encoding="utf-8")


def test_meridiano_em_dois_arquivos_iguais_falha_por_fitid_repetido(dados, tmp_path):
    import pytest
    from tarvo.ingest.erros import LayoutError
    pasta = _pasta(dados, tmp_path / "c")
    shutil.copy(pasta / "05b_extrato_banco_meridiano_cc90233_set2026.ofx", pasta / "05b_copia.ofx")
    with pytest.raises(LayoutError, match="FITID"):
        fechar("2026-09", pasta, pasta / "saida", cliente=None)
