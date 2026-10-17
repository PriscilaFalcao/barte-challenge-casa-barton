import random
from datetime import date
from decimal import Decimal as D

import pytest

from tarvo.config import OverrideTaxa
from tarvo.core.excecoes import TipoExcecao
from tarvo.engines.divergencias import CONTRATO, ISENCAO, calcular_divergencias
from tarvo.output.validators import ValidationError, validar_i_d1, validar_i_r1
from tests.helpers import CNPJ, contrato, rodar_checkout, tx

ZERO_DEB = OverrideTaxa(CNPJ, ("DEBITO", "ANTECIPACAO"), D("0"), date(2026, 9, 1), date(2026, 12, 31), "C8", "Slack")


def _div(txs, contratos=None, overrides=(), **kw):
    res, rastro = rodar_checkout(txs, contratos, overrides)
    return calcular_divergencias(res.linhas, rastro, "2026-09", {CNPJ: "Loja Um"}, **kw), rastro


def test_truncation_cent_is_not_a_divergence():
    # 1,00% de 123,45 = 1,2345 -> comissão 1,23; a Orbe truncaria para 1,23 ou até 1,22. Taxa igual: nada.
    r, _ = _div([tx(bruto="123.45", aplicada="1.00", valor_taxa="1.22")])
    assert r.divergencias == [] and r.excecoes == []


def test_overcharge_is_positive_and_rounded_per_line():
    r, _ = _div([tx(bruto="1000.00", aplicada="1.50")])  # contratado 1,00%
    (d,) = r.divergencias
    assert d["diferenca_brl"] == D("5.00")
    assert (d["taxa_contratada_pct"], d["taxa_aplicada_pct"]) == ("1.00", "1.50")


def test_undercharge_is_negative():
    r, _ = _div([tx(bruto="1000.00", aplicada="0.50")])
    assert r.divergencias[0]["diferenca_brl"] == D("-5.00")


def test_half_cent_rounds_up_symmetrically():
    r, _ = _div([tx("TX1", bruto="0.50", aplicada="2.00"), tx("TX2", bruto="-0.50", aplicada="2.00", tipo="ESTORNO", ref="X", orig=date(2026, 9, 1))])
    por_ref = {d["ref_origem"]: d["diferenca_brl"] for d in r.divergencias}
    assert por_ref == {"TX1": D("0.01"), "TX2": D("-0.01")}


def test_estorno_at_wrong_rate_is_a_negative_divergence():
    r, _ = _div([tx(tipo="ESTORNO", bruto="-1000.00", aplicada="1.50", ref="X", orig=date(2026, 9, 1))])
    assert r.divergencias[0]["diferenca_brl"] == D("-5.00")  # D4 / V15: Orbe já devolveu parte do excesso


def test_estorno_divergence_can_be_switched_off_for_v15():
    r, _ = _div([tx(tipo="ESTORNO", bruto="-1000.00", aplicada="1.50", ref="X", orig=date(2026, 9, 1))],
                incluir_estornos=False)
    assert r.divergencias == []


def test_zero_contract_makes_everything_charged_a_divergence():
    txs = [tx("TX1", bruto="200.00", aplicada="1.49"), tx("AN1", tipo="ANTECIPACAO", mod="", parc=None, bruto="1000.00", aplicada="2.10")]
    r, _ = _div(txs, overrides=[ZERO_DEB])
    assert {d["ref_origem"]: d["diferenca_brl"] for d in r.divergencias} == {"TX1": D("2.98"), "AN1": D("21.00")}


def test_row_shape_and_ids():
    r, _ = _div([tx("TX88428053", bruto="1000.00", aplicada="1.50")])
    d = r.divergencias[0]
    assert d["id_saida"] == "DIV-CHK-TX88428053"
    assert (d["cnpj"], d["linha_negocio"], d["ref_origem"]) == (CNPJ, "CHECKOUT", "TX88428053")


def test_rastro_has_one_line_per_divergence_with_the_difference():
    r, rastro = _div([tx("TX1", bruto="1000.00", aplicada="1.50")])
    (l,) = [l for l in rastro.linhas() if l.id_saida == "DIV-CHK-TX1"]
    assert (l.ref_origem, l.valor, l.regra_id) == ("TX1", D("5.00"), "D1")
    validar_i_r1({"divergencias_taxa": r.divergencias}, rastro)


def test_one_pending_per_merchant_with_net_value_and_every_transaction_in_rastro():
    """✅ Casa Barton 11h01: uma pendência por contraparte e lojista; ✅ P2: venda e estorno se anulam."""
    r, rastro = _div([tx("TX1", bruto="1000.00", aplicada="1.50"), tx("TX2", bruto="500.00", aplicada="1.50"),
                      tx("TX3", tipo="ESTORNO", bruto="-200.00", aplicada="1.50", ref="TX1", orig=date(2026, 9, 2))])
    (e,) = r.excecoes
    assert (e.tipo, e.ref_origem, e.valor_brl, e.quem_decide) == (
        TipoExcecao.DIVERGENCIA_ORBE, f"{CNPJ}-202609", D("6.50"), "Financeiro")
    assert e.id_saida == f"PEN-DIVERGENCIA_ORBE-{CNPJ}-202609"
    assert sorted(l.ref_origem for l in rastro.linhas() if l.id_saida == e.id_saida) == ["TX1", "TX2", "TX3"]
    assert rastro.soma(e.id_saida) == D("6.50")
    assert "Loja Um" in e.motivo and "1.50% x 1.00%" in e.motivo and "3 transação" in e.motivo


def test_contract_divergence_is_marked_as_such():
    r, _ = _div([tx(bruto="1000.00", aplicada="1.50")])
    assert r.divergencias[0]["natureza"] == CONTRATO


def test_override_divergence_is_a_merchant_refund_not_an_orbe_charge():
    """✅ Helena 10h58 (Casa): listada e marcada em divergências, pendência única com o total, fora da Orbe."""
    # valor_taxa = o que a Orbe descontou de fato (trunca): a devolução usa ele, não a fórmula (Helena 12h50)
    txs = [tx("TX1", bruto="200.00", aplicada="1.49", valor_taxa="2.98"),
           tx("TX2", bruto="300.00", aplicada="1.49", valor_taxa="4.46")]
    r, rastro = _div(txs, overrides=[ZERO_DEB])
    assert {d["natureza"] for d in r.divergencias} == {ISENCAO}
    assert sum(d["diferenca_brl"] for d in r.divergencias) == D("7.45")  # fórmula, na lista de divergências
    (e,) = r.excecoes
    assert (e.tipo, e.valor_brl, e.quem_decide) == (TipoExcecao.DEVOLUCAO_LOJISTA, D("7.44"), "Financeiro e Comercial")
    assert "não entra na cobrança à Orbe" in e.motivo and rastro.soma(e.id_saida) == D("7.44")


def test_same_merchant_with_both_natures_gets_two_pendings():
    ovr = OverrideTaxa(CNPJ, ("DEBITO",), D("0"), date(2026, 9, 1), date(2026, 12, 31), "C8", "Slack")
    r, _ = _div([tx("TX1", bruto="100.00", aplicada="1.50"), tx("TX2", mod="PIX", bruto="100.00", aplicada="1.50")],
                overrides=[ovr])
    assert sorted(e.tipo for e in r.excecoes) == [TipoExcecao.DEVOLUCAO_LOJISTA, TipoExcecao.DIVERGENCIA_ORBE]


def test_order_independent():
    txs = [tx(f"TX{i}", bruto=f"{100 + i}.11", aplicada="1.30") for i in range(20)]
    a, _ = _div(txs)
    emb = txs[:]
    random.Random(3).shuffle(emb)
    b, _ = _div(emb)
    assert a.divergencias == b.divergencias and [e.id_saida for e in a.excecoes] == [e.id_saida for e in b.excecoes]


def test_i_d1_rejects_a_divergence_with_equal_rates():
    ruim = [{"id_saida": "DIV-CHK-TX1", "taxa_contratada_pct": "1.00", "taxa_aplicada_pct": "1.00", "ref_origem": "TX1"}]
    with pytest.raises(ValidationError, match="TX1"):
        validar_i_d1(ruim)


def test_i_d1_accepts_real_divergences():
    validar_i_d1([{"id_saida": "D", "taxa_contratada_pct": "1.00", "taxa_aplicada_pct": "1.50", "ref_origem": "TX1"}])
