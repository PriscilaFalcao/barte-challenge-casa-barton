from decimal import Decimal

import pytest

from tarvo.core.rastro import Rastro
from tarvo.output.validators import ValidationError, validar_i_r1


def _rastro():
    r = Rastro()
    r.add("COM-A", "o.csv", "TX1", Decimal("1.10"))
    r.add("COM-A", "o.csv", "TX2", Decimal("2.20"))
    return r


def test_i_r1_passes_when_sums_match():
    validar_i_r1({"comissoes_por_lojista": [{"id_saida": "COM-A", "comissao_brl": Decimal("3.30")}]}, _rastro())


def test_i_r1_fails_on_one_cent_difference():
    with pytest.raises(ValidationError, match="COM-A"):
        validar_i_r1({"comissoes_por_lojista": [{"id_saida": "COM-A", "comissao_brl": Decimal("3.31")}]}, _rastro())


def test_i_r1_fails_when_output_id_has_no_rastro():
    with pytest.raises(ValidationError, match="COM-ORFA"):
        validar_i_r1({"comissoes_por_lojista": [{"id_saida": "COM-ORFA", "comissao_brl": Decimal("0")}]}, _rastro())


def test_i_r1_fails_on_duplicate_id_in_same_output():
    linha = {"id_saida": "COM-A", "comissao_brl": Decimal("3.30")}
    with pytest.raises(ValidationError, match="duplicado"):
        validar_i_r1({"comissoes_por_lojista": [linha, linha]}, _rastro())


def test_i_r1_uses_the_right_value_column_per_output():
    r = Rastro()
    r.add("DIV-X", "o.csv", "TX9", Decimal("0.50"))
    validar_i_r1({"divergencias_taxa": [{"id_saida": "DIV-X", "diferenca_brl": Decimal("0.50")}]}, r)


def test_i_r1_reports_all_failures_at_once():
    saidas = {"comissoes_por_lojista": [
        {"id_saida": "COM-A", "comissao_brl": Decimal("9")},
        {"id_saida": "COM-B", "comissao_brl": Decimal("9")},
    ]}
    with pytest.raises(ValidationError) as e:
        validar_i_r1(saidas, _rastro())
    assert "COM-A" in str(e.value) and "COM-B" in str(e.value)
