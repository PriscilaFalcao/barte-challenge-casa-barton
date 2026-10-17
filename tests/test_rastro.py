from decimal import Decimal

import pytest

from tarvo.core.rastro import Rastro


def test_sum_by_id_is_exact_decimal():
    r = Rastro()
    r.add("COM-X", "01_orbe.csv", "TX1", Decimal("0.10"))
    r.add("COM-X", "01_orbe.csv", "TX2", Decimal("0.20"))
    assert r.soma("COM-X") == Decimal("0.30")


def test_same_ref_twice_with_different_component_is_allowed():
    r = Rastro()
    r.add("COM-X", "o.csv", "TX1", Decimal("1.00"), componente="MDR")
    r.add("COM-X", "o.csv", "TX1", Decimal("0.50"), componente="ANTECIPACAO")
    assert r.soma("COM-X") == Decimal("1.50")


def test_exact_duplicate_line_is_rejected():
    r = Rastro()
    r.add("COM-X", "o.csv", "TX1", Decimal("1.00"), componente="MDR")
    with pytest.raises(ValueError):
        r.add("COM-X", "o.csv", "TX1", Decimal("1.00"), componente="MDR")


def test_rejects_float_value():
    with pytest.raises(TypeError):
        Rastro().add("COM-X", "o.csv", "TX1", 1.0)


def test_unknown_id_sums_to_zero_and_ids_listed():
    r = Rastro()
    r.add("B", "o.csv", "1", Decimal("1"))
    r.add("A", "o.csv", "2", Decimal("1"))
    assert r.soma("Z") == Decimal("0")
    assert r.ids() == ["A", "B"]
