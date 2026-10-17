from decimal import Decimal

import pytest

from tarvo.core.money import D, fmt, parse_br, round_money


def test_round_half_up_positive():
    assert round_money(Decimal("0.005")) == Decimal("0.01")


def test_round_half_up_is_symmetric_on_negatives():
    assert round_money(Decimal("-0.005")) == Decimal("-0.01")


def test_round_below_half_goes_down():
    assert round_money(Decimal("0.0049999")) == Decimal("0.00")


def test_D_rejects_float():
    with pytest.raises(TypeError):
        D(0.1)


def test_D_accepts_str_and_int():
    assert D("1.49") == Decimal("1.49")
    assert D(3) == Decimal(3)


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("66.026,00", "66026.00"),
        ("-7.108,69", "-7108.69"),
        ("1,49%", "1.49"),
        (" 0,5 ", "0.5"),
    ],
)
def test_parse_br(texto, esperado):
    assert parse_br(texto) == Decimal(esperado)


def test_parse_br_rejects_garbage():
    with pytest.raises(ValueError):
        parse_br("abc")


def test_fmt_always_two_places_with_dot():
    assert fmt(Decimal("5.5")) == "5.50"
    assert fmt(Decimal("-0.001")) == "0.00"
    assert fmt(Decimal("214558.33")) == "214558.33"


def test_fmt_pct_keeps_at_least_two_places():
    from tarvo.core.money import fmt_pct

    assert fmt_pct(Decimal("1.4900")) == "1.49"
    assert fmt_pct(Decimal("2.1")) == "2.10"
    assert fmt_pct(Decimal("0")) == "0.00"
    assert fmt_pct(Decimal("1.2345")) == "1.2345"
