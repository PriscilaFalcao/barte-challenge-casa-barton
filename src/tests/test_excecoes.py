from decimal import Decimal

import pytest

from tarvo.core.excecoes import QUEM_DECIDE_DEFAULT, Excecao, TipoExcecao


def test_every_type_has_default_owner():
    for t in TipoExcecao:
        assert QUEM_DECIDE_DEFAULT[t]


def test_owner_defaults_follow_prd_table():
    assert QUEM_DECIDE_DEFAULT[TipoExcecao.DIVERGENCIA_ORBE] == "Financeiro"
    assert QUEM_DECIDE_DEFAULT[TipoExcecao.SEM_CONTRATO] == "Comercial"
    assert QUEM_DECIDE_DEFAULT[TipoExcecao.CONTRATO_AMBIGUO] == "Comercial"  # ✅ cadastro e contrato: comercial
    assert QUEM_DECIDE_DEFAULT[TipoExcecao.ENTIDADE_NAO_RESOLVIDA] == "Comercial"
    assert QUEM_DECIDE_DEFAULT[TipoExcecao.DEVOLUCAO_LOJISTA] == "Financeiro e Comercial"


def test_excecao_fills_owner_and_id():
    e = Excecao.nova(
        TipoExcecao.CONTESTACAO_PONTE, "PC-0926-0162", Decimal("410.94"), "Operação duplicada"
    )
    assert e.quem_decide == "Financeiro"
    assert e.id_saida == "PEN-CONTESTACAO_PONTE-PC-0926-0162"


def test_excecao_requires_reason():
    with pytest.raises(ValueError):
        Excecao.nova(TipoExcecao.SEM_CONTRATO, "EC1", Decimal("0"), "")
