from datetime import date
from decimal import Decimal

import pytest

from tarvo.config import carregar_defaults


def test_defaults_carry_confirmed_rules():
    cfg = carregar_defaults()
    assert cfg.ecs_extra["1043396662"] == "78576234000179"
    assert cfg.sem_contrato == {"1076801732": "Atlas Idiomas"}
    (o,) = cfg.overrides
    assert o.cnpj14 == "00520815000100"
    assert o.taxa_pct == Decimal("0")
    assert (o.inicio, o.fim) == (date(2026, 9, 1), date(2026, 12, 31))
    assert set(o.produtos) == {"DEBITO", "CREDITO_1X", "CREDITO_2_6X", "CREDITO_7_12X", "PIX", "ANTECIPACAO"}
    assert o.regra_id == "C8"


def test_unknown_product_in_override_fails(tmp_path):
    p = tmp_path / "d.yaml"
    p.write_text('overrides_taxa:\n  - {cnpj: "1", produtos: [BOLETO], taxa_pct: "0", inicio: 2026-09-01, fim: 2026-12-31, regra_id: X, fonte: f}\n')
    with pytest.raises(ValueError, match="BOLETO"):
        carregar_defaults(p)
