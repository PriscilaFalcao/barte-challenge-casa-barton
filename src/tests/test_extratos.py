"""Leitores do B6: plano de contas (Latin-1), Aurora (CSV com cabeçalho do banco) e Meridiano (OFX SGML)."""
from datetime import date
from decimal import Decimal as D

import pytest

from tarvo.core.ledger import Ledger
from tarvo.ingest.aurora import ler_aurora
from tarvo.ingest.erros import LayoutError
from tarvo.ingest.meridiano import ler_meridiano
from tarvo.ingest.plano_contas import ler_plano_contas

CAB_AURORA = """Banco Aurora S.A.;;;;
Extrato;;;;
;;;;
Data;Lançamento;Documento;Valor (R$);Saldo (R$)
31/08/2026;SALDO ANTERIOR;;;1.000,00
"""
RODAPE_AURORA = """;;;;
;SALDO FINAL;;;{final}
;Os lançamentos estão sujeitos a confirmação.;;;
"""


def _aurora(tmp_path, corpo, final="1.150,50"):
    p = tmp_path / "05a.csv"
    p.write_text(CAB_AURORA + corpo + RODAPE_AURORA.format(final=final), encoding="utf-8")
    return p


def test_aurora_reads_rows_with_physical_line_refs_and_pt_br_values(tmp_path):
    corpo = "01/09/2026;TED RECEBIDA ORBE;123;200,50;1.200,50\n02/09/2026;TAR PACOTE;;-50,00;1.150,50\n"
    ledger = Ledger()
    ext = ler_aurora(_aurora(tmp_path, corpo), ledger)
    assert [(l.ref_origem, l.data, l.valor) for l in ext.lancamentos] == [
        ("L6", date(2026, 9, 1), D("200.50")), ("L7", date(2026, 9, 2), D("-50.00"))]
    assert (ext.saldo_inicial, ext.saldo_final) == (D("1000.00"), D("1150.50"))
    assert ledger.contar("Aurora", "saldo anterior ou final") == 2
    assert ledger.contar("Aurora", "rodapé ou linha sem dado") == 1  # o aviso; a linha em branco não conta


def test_aurora_broken_balance_chain_fails(tmp_path):
    corpo = "01/09/2026;TED;;200,00;1.300,00\n"
    with pytest.raises(LayoutError, match="cadeia de saldos não fecha em L6"):
        ler_aurora(_aurora(tmp_path, corpo, final="1.300,00"))


def test_aurora_final_balance_must_match(tmp_path):
    with pytest.raises(LayoutError, match="SALDO FINAL"):
        ler_aurora(_aurora(tmp_path, "01/09/2026;TED;;200,00;1.200,00\n", final="9,99"))


def test_aurora_row_with_value_but_no_date_fails_instead_of_vanishing(tmp_path):
    with pytest.raises(LayoutError, match="L6 tem valor"):
        ler_aurora(_aurora(tmp_path, ";PIX ENVIADO X;;-10,00;990,00\n", final="990,00"))


def test_aurora_header_found_by_text_not_line_number(tmp_path):
    p = tmp_path / "05a.csv"
    p.write_text("x;;;;\n" * 3 + CAB_AURORA + "01/09/2026;TED;;1,00;1.001,00\n", encoding="utf-8")
    assert ler_aurora(p).lancamentos[0].ref_origem == "L9"


def test_aurora_missing_column_fails(tmp_path):
    p = tmp_path / "05a.csv"
    p.write_text("Data;Lançamento;Documento;Saldo (R$)\n", encoding="utf-8")
    with pytest.raises(LayoutError, match="Valor"):
        ler_aurora(p)


OFX = """OFXHEADER:100\r\nDATA:OFXSGML\r\n\r\n<OFX>\r\n<BANKMSGSRSV1><STMTTRNRS><STMTRS>\r\n<BANKTRANLIST>\r\n{trs}</BANKTRANLIST>\r\n<LEDGERBAL>\r\n<BALAMT>500.00\r\n</LEDGERBAL>\r\n</STMTRS></STMTTRNRS></BANKMSGSRSV1>\r\n</OFX>\r\n"""


def _tr(fitid="MRD1", tipo="CREDIT", valor="100.00", memo="PIX RECEB MUNDO ABERTO INTERCÂMBIO", fechar=True):
    t = f"<STMTTRN>\r\n<TRNTYPE>{tipo}\r\n<DTPOSTED>20260901120000[-3:BRT]\r\n<TRNAMT>{valor}\r\n<FITID>{fitid}\r\n<MEMO>{memo}\r\n"
    return t + ("</STMTTRN>\r\n" if fechar else "")


def _ofx(tmp_path, *trs):
    p = tmp_path / "05b.ofx"
    p.write_bytes(OFX.format(trs="".join(trs)).encode("cp1252"))
    return p


def test_meridiano_reads_cp1252_memo_and_fitid(tmp_path):
    ext = ler_meridiano(_ofx(tmp_path, _tr(), _tr("MRD2", "DEBIT", "-40.10", "TARIFA PACOTE CAMBIO")))
    assert [(l.ref_origem, l.valor, l.descricao) for l in ext.lancamentos] == [
        ("MRD1", D("100.00"), "PIX RECEB MUNDO ABERTO INTERCÂMBIO"), ("MRD2", D("-40.10"), "TARIFA PACOTE CAMBIO")]
    assert ext.saldo_final == D("500.00") and ext.lancamentos[0].data == date(2026, 9, 1)


def test_meridiano_accepts_unclosed_stmttrn(tmp_path):
    ext = ler_meridiano(_ofx(tmp_path, _tr(fechar=False), _tr("MRD2", fechar=False)))
    assert [l.ref_origem for l in ext.lancamentos] == ["MRD1", "MRD2"]


def test_meridiano_duplicate_fitid_fails(tmp_path):
    with pytest.raises(LayoutError, match="FITID duplicado MRD1"):
        ler_meridiano(_ofx(tmp_path, _tr(), _tr()))


def test_meridiano_missing_fitid_fails(tmp_path):
    with pytest.raises(LayoutError, match="FITID ausente"):
        ler_meridiano(_ofx(tmp_path, _tr(fitid="")))


def test_meridiano_sign_must_match_trntype(tmp_path):
    with pytest.raises(LayoutError, match="TRNTYPE DEBIT"):
        ler_meridiano(_ofx(tmp_path, _tr(tipo="DEBIT", valor="10.00")))


def test_meridiano_not_ofx_fails(tmp_path):
    p = tmp_path / "x.ofx"
    p.write_text("Data;Valor\n")
    with pytest.raises(LayoutError, match="OFX"):
        ler_meridiano(p)


def test_plano_reads_latin1_and_marks_analytic(tmp_path):
    p = tmp_path / "04.csv"
    p.write_bytes("COD_CONTA;DESCRICAO;TIPO;NATUREZA;ACEITA_LANCTO\r\n1.1;ATIVO CIRCULANTE;SINTETICA;D;N\r\n"
                  "4.3.01;IOF;ANALITICA;D;S\r\n1.1.02;APLICAÇÕES;SINTETICA;D;N\r\n".encode("latin-1"))
    plano = ler_plano_contas(p)
    assert plano["4.3.01"].analitica and not plano["1.1"].analitica
    assert plano["1.1.02"].descricao == "APLICAÇÕES"


def test_plano_missing_column_fails(tmp_path):
    p = tmp_path / "04.csv"
    p.write_bytes(b"COD_CONTA;DESCRICAO\r\n1;ATIVO\r\n")
    with pytest.raises(LayoutError, match="ACEITA_LANCTO"):
        ler_plano_contas(p)


def test_real_pack_reads(dados):
    a = ler_aurora(dados / "05a_extrato_banco_aurora_cc4471_set2026.csv")
    m = ler_meridiano(dados / "05b_extrato_banco_meridiano_cc90233_set2026.ofx")
    plano = ler_plano_contas(dados / "04_plano_de_contas_fenix_erp.csv")
    assert (len(a.lancamentos), a.lancamentos[0].ref_origem, a.lancamentos[-1].ref_origem) == (84, "L9", "L92")
    assert (a.saldo_inicial, a.saldo_final) == (D("612334.81"), D("-1920088.60"))
    assert len(m.lancamentos) == 100 and m.saldo_final == D("1320453.26")
    assert (len(plano), sum(c.analitica for c in plano.values())) == (52, 32)
