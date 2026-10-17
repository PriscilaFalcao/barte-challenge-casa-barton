from datetime import date
from decimal import Decimal

import pytest

from tarvo.ingest.erros import LayoutError
from tarvo.ingest.orbe import ler_orbe

CAB = ("id_transacao;data_movimento;cod_estabelecimento;nome_estabelecimento;tipo_lancamento;"
       "modalidade;qtd_parcelas;bandeira;valor_bruto;taxa_aplicada_pct;valor_taxa;valor_liquido;"
       "id_referencia;data_venda_original")


def _csv(tmp_path, *linhas, cab=CAB):
    p = tmp_path / "orbe.csv"
    p.write_bytes(("\r\n".join([cab, *linhas]) + "\r\n").encode("utf-8"))
    return p


def test_parses_venda(tmp_path):
    p = _csv(tmp_path, "TX1;01/09/2026;1018325654;CASA;VENDA;CREDITO PARCELADO;11;ELO;5773,57;3,79;218,81;5554,76;;")
    (t,) = ler_orbe(p)
    assert t.id_transacao == "TX1"
    assert t.data_movimento == date(2026, 9, 1)
    assert t.cod_estabelecimento == "1018325654"
    assert t.tipo == "VENDA"
    assert t.qtd_parcelas == 11
    assert t.valor_bruto == Decimal("5773.57")
    assert t.taxa_aplicada_pct == Decimal("3.79")
    assert t.valor_taxa == Decimal("218.81")
    assert t.id_referencia is None and t.data_venda_original is None


def test_parses_estorno_with_reference_and_negative_values(tmp_path):
    p = _csv(tmp_path, "TX2;01/09/2026;1000960410;OXFORD;ESTORNO;CREDITO PARCELADO;10;VISA;-2193,16;3,79;-83,12;-2110,04;TX1;22/08/2026")
    (t,) = ler_orbe(p)
    assert t.valor_bruto == Decimal("-2193.16")
    assert t.id_referencia == "TX1"
    assert t.data_venda_original == date(2026, 8, 22)


def test_antecipacao_has_no_modalidade_and_reversao_type_is_normalized(tmp_path):
    p = _csv(tmp_path,
             "AN1;01/09/2026;1061760196;CANGURU;ANTECIPACAO;;;;31765,12;2,10;667,06;31098,06;;",
             "AN2;05/09/2026;1038867654;KIWI;REVERSAO ANTECIPACAO;;;;-52314,21;2,10;-1098,59;-51215,62;AN1;04/09/2026")
    a, r = ler_orbe(p)
    assert a.tipo == "ANTECIPACAO" and a.modalidade == "" and a.qtd_parcelas is None
    assert r.tipo == "REVERSAO_ANTECIPACAO"


def test_missing_column_fails_naming_it(tmp_path):
    p = _csv(tmp_path, "x", cab=CAB.replace(";taxa_aplicada_pct", ""))
    with pytest.raises(LayoutError, match="taxa_aplicada_pct"):
        ler_orbe(p)


def test_unknown_tipo_fails(tmp_path):
    p = _csv(tmp_path, "TX1;01/09/2026;1;N;CHARGEBACK;PIX;1;;1,00;0,89;0,01;0,99;;")
    with pytest.raises(LayoutError, match="CHARGEBACK"):
        ler_orbe(p)


def test_duplicate_id_fails(tmp_path):
    linha = "TX1;01/09/2026;1;N;VENDA;PIX;1;;1,00;0,89;0,01;0,99;;"
    with pytest.raises(LayoutError, match="TX1"):
        ler_orbe(_csv(tmp_path, linha, linha))


def test_bad_date_fails_with_context(tmp_path):
    p = _csv(tmp_path, "TX1;2026-09-01;1;N;VENDA;PIX;1;;1,00;0,89;0,01;0,99;;")
    with pytest.raises(LayoutError, match="TX1"):
        ler_orbe(p)


def test_real_file_golden(dados):
    txs = ler_orbe(dados / "01_orbe_relatorio_comissoes_set2026.csv")
    assert len(txs) == 1943
    assert len({t.id_transacao for t in txs}) == 1943
