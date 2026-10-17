import pytest

from tarvo.core.ids import (
    id_comissao, id_divergencia, id_lancamento, id_nota_checkout,
    id_nota_remessa, id_pendencia, norm_cnpj,
)


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("66.564.512/0001-99", "66564512000199"),
        ("66564512000199", "66564512000199"),
        (6564512000199, "06564512000199"),  # numérico que perdeu o zero à esquerda
        (" 75374179000146 ", "75374179000146"),
    ],
)
def test_norm_cnpj(entrada, esperado):
    assert norm_cnpj(entrada) == esperado


def test_norm_cnpj_rejects_too_long_or_empty():
    with pytest.raises(ValueError):
        norm_cnpj("123456789012345")
    with pytest.raises(ValueError):
        norm_cnpj("")


def test_ids_match_prd_examples():
    assert id_comissao("CHECKOUT", "66564512000199", "2026-09") == "COM-CHK-66564512000199-202609"
    assert id_comissao("REMESSA", "66564512000199", "2026-09") == "COM-REM-66564512000199-202609"
    assert id_divergencia("CHECKOUT", "TX88428053") == "DIV-CHK-TX88428053"
    assert id_nota_checkout("66564512000199", "2026-09") == "NF-CHK-66564512000199-202609"
    assert id_nota_remessa("2026-09") == "NF-REM-202609"
    assert id_lancamento("AURORA", "L34") == "LAN-AUR-L34"
    assert id_lancamento("MERIDIANO", "MRD2026090425") == "LAN-MER-MRD2026090425"
    assert id_pendencia("CONTESTACAO_PONTE", "PC-0926-0162") == "PEN-CONTESTACAO_PONTE-PC-0926-0162"


def test_unknown_enum_rejected():
    with pytest.raises(ValueError):
        id_comissao("OUTRA", "66564512000199", "2026-09")
    with pytest.raises(ValueError):
        id_lancamento("ITAU", "L1")
