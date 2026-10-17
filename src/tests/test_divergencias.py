import random
from datetime import date
from decimal import Decimal as D

import pytest

from tarvo.config import OverrideTaxa
from tarvo.core.excecoes import TipoExcecao
from tarvo.engines.divergencias import calcular_divergencias
from tarvo.output.validators import ValidationError, validar_i_d1, validar_i_r1
from tests.helpers import CNPJ, contrato, rodar_checkout, tx

ZERO_DEB = OverrideTaxa(CNPJ, ("DEBITO", "ANTECIPACAO"), D("0"), date(2026, 9, 1), date(2026, 12, 31), "C8", "Slack")


def _div(txs, contratos=None, overrides=(), **kw):
    res, rastro = rodar_checkout(txs, contratos, overrides)
    return calcular_divergencias(res.linhas, rastro, **kw), rastro


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


def test_each_divergence_is_a_pending_for_helena_with_rastro():
    r, rastro = _div([tx("TX1", bruto="1000.00", aplicada="1.50")])
    (e,) = r.excecoes
    assert (e.tipo, e.ref_origem, e.valor_brl, e.quem_decide) == (TipoExcecao.DIVERGENCIA_ORBE, "TX1", D("5.00"), "Helena")
    assert rastro.soma(e.id_saida) == D("5.00")
    assert "1.50" in e.motivo and "1.00" in e.motivo


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
