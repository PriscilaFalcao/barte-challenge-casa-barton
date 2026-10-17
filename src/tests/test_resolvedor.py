from datetime import date
from decimal import Decimal

import pytest

from tarvo.config import OverrideTaxa
from tarvo.contracts.resolver import ContratoError, Resolvedor, produto_de
from tarvo.core.excecoes import TipoExcecao
from tarvo.ingest.taxas import ContratoLinha

CNPJ = "22224579000109"


def _linha(ref, ini=None, fim=None, cv="2.59", spread=None, valida=True, pix="0.89", cnpj=CNPJ):
    taxas = {"DEBITO": Decimal("1.49"), "CREDITO_1X": Decimal(cv), "CREDITO_2_6X": Decimal("3.19"),
             "CREDITO_7_12X": Decimal("3.79"), "PIX": Decimal(pix) if pix else None,
             "ANTECIPACAO": Decimal("2.10")}
    return ContratoLinha(ref, "Loja", cnpj, "1", taxas, Decimal(spread) if spread else None,
                         "x", ini, fim, valida, None)


BRIDGE = [_linha("Taxas!L5", fim=date(2026, 9, 14), cv="2.59"), _linha("Taxas!L6", ini=date(2026, 9, 15), cv="2.19")]


@pytest.mark.parametrize(
    "modalidade,parcelas,esperado",
    [
        ("DEBITO", 1, "DEBITO"), ("PIX", 1, "PIX"), ("CREDITO A VISTA", 1, "CREDITO_1X"),
        ("CREDITO PARCELADO", 2, "CREDITO_2_6X"), ("CREDITO PARCELADO", 6, "CREDITO_2_6X"),
        ("CREDITO PARCELADO", 7, "CREDITO_7_12X"), ("CREDITO PARCELADO", 12, "CREDITO_7_12X"),
    ],
)
def test_produto_de(modalidade, parcelas, esperado):
    assert produto_de(modalidade, parcelas) == esperado


@pytest.mark.parametrize("modalidade,parcelas", [("CREDITO PARCELADO", 13), ("CREDITO PARCELADO", 1),
                                                  ("CREDITO PARCELADO", None), ("BOLETO", 1)])
def test_produto_de_out_of_range_is_exception(modalidade, parcelas):
    with pytest.raises(ContratoError) as e:
        produto_de(modalidade, parcelas)
    assert e.value.tipo == TipoExcecao.CONTRATO_AMBIGUO


def test_picks_line_by_sale_date_and_window_edges_are_inclusive():
    r = Resolvedor(BRIDGE)
    assert r.taxa(CNPJ, "CREDITO_1X", date(2026, 9, 14)).pct == Decimal("2.59")
    assert r.taxa(CNPJ, "CREDITO_1X", date(2026, 9, 15)).pct == Decimal("2.19")
    t = r.taxa(CNPJ, "CREDITO_1X", date(2026, 9, 15))
    assert t.ref_origem == "Taxas!L6"


def test_old_sale_date_uses_old_line():
    assert Resolvedor(BRIDGE).taxa(CNPJ, "CREDITO_1X", date(2026, 8, 20)).pct == Decimal("2.59")


def test_unchanged_product_is_same_on_both_lines():
    r = Resolvedor(BRIDGE)
    assert r.taxa(CNPJ, "DEBITO", date(2026, 9, 1)).pct == r.taxa(CNPJ, "DEBITO", date(2026, 9, 20)).pct


def test_overlapping_windows_is_ambiguous():
    r = Resolvedor([_linha("Taxas!L5"), _linha("Taxas!L6", ini=date(2026, 9, 1))])
    with pytest.raises(ContratoError, match="Taxas!L5") as e:
        r.taxa(CNPJ, "DEBITO", date(2026, 9, 10))
    assert e.value.tipo == TipoExcecao.CONTRATO_AMBIGUO


def test_no_window_covers_date():
    r = Resolvedor([_linha("Taxas!L5", ini=date(2026, 6, 1))])
    with pytest.raises(ContratoError, match="nenhuma linha"):
        r.taxa(CNPJ, "DEBITO", date(2026, 5, 31))


def test_unknown_merchant():
    with pytest.raises(ContratoError):
        Resolvedor(BRIDGE).taxa("99999999000199", "DEBITO", date(2026, 9, 1))


def test_invalid_line_is_not_used():
    r = Resolvedor([_linha("Taxas!L5", valida=False)])
    with pytest.raises(ContratoError):
        r.taxa(CNPJ, "DEBITO", date(2026, 9, 1))


def test_product_not_contracted_is_exception():
    r = Resolvedor([_linha("Taxas!L5", pix=None)])
    with pytest.raises(ContratoError, match="PIX"):
        r.taxa(CNPJ, "PIX", date(2026, 9, 1))


OVR = OverrideTaxa(CNPJ, ("DEBITO", "ANTECIPACAO"), Decimal("0"), date(2026, 9, 1), date(2026, 12, 31), "C8", "Slack")


def test_override_wins_inside_its_window_only():
    r = Resolvedor([_linha("Taxas!L5")], overrides=[OVR])
    t = r.taxa(CNPJ, "DEBITO", date(2026, 9, 1))
    assert (t.pct, t.regra_id) == (Decimal("0"), "C8")
    assert r.taxa(CNPJ, "DEBITO", date(2026, 8, 31)).pct == Decimal("1.49")
    assert r.taxa(CNPJ, "DEBITO", date(2026, 12, 31)).pct == Decimal("0")
    assert r.taxa(CNPJ, "DEBITO", date(2027, 1, 1)).pct == Decimal("1.49")


def test_override_only_covers_listed_products():
    r = Resolvedor([_linha("Taxas!L5")], overrides=[OVR])
    assert r.taxa(CNPJ, "CREDITO_1X", date(2026, 9, 10)).pct == Decimal("2.59")


def test_plain_rate_reports_planilha_rule():
    assert Resolvedor(BRIDGE).taxa(CNPJ, "DEBITO", date(2026, 9, 1)).regra_id == "PLANILHA"


def test_spread_blank_is_standard_1_5_and_number_is_literal():
    padrao = Resolvedor([_linha("Taxas!L5")]).spread(CNPJ, date(2026, 9, 1))
    assert (padrao.pct, padrao.regra_id) == (Decimal("1.5"), "R2")
    assert Resolvedor([_linha("Taxas!L5", spread="1.2")]).spread(CNPJ, date(2026, 9, 1)).pct == Decimal("1.2")
