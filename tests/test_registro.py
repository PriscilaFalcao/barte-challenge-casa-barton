from decimal import Decimal

import pytest

from tarvo.identity.registro import Registro, norm_nome
from tarvo.ingest.taxas import ContratoLinha


def _c(nome, cnpj, ec=None, inativo=False, ref="Taxas!L1"):
    return ContratoLinha(ref, nome, cnpj, ec, {}, None, "01/01/2026", None, None, True, None, inativo)


def _reg(**kw):
    contratos = [
        _c("Escola Bridge de Idiomas Ltda", "22224579000109", "1075624862", ref="Taxas!L5"),
        _c("Bridge Idiomas (NOVA)", "22224579000109", "1075624862", ref="Taxas!L6"),
        _c("Horizonte Viagens", "78576234000179"),
        _c("Globo Trotter", "22348118000148", "1157874034", inativo=True),
    ]
    return Registro.construir(contratos, ecs_extra={"1043396662": "78576234000179"},
                              sem_contrato={"1076801732": "Atlas Idiomas"}, **kw)


def test_norm_nome_ignores_case_accent_punctuation_spaces():
    assert norm_nome("Bem-Vindo  Exchange") == norm_nome("BEM VINDO EXCHANGE")
    assert norm_nome("Nórdica") == norm_nome("NORDICA")


def test_two_rows_same_cnpj_make_one_merchant_with_first_name():
    r = _reg()
    loj = r.por_cnpj("22224579000109")
    assert loj.nome_canonico == "Escola Bridge de Idiomas Ltda"
    assert loj.ecs == ("1075624862",)


def test_resolves_by_ec_including_extra_ecs():
    r = _reg()
    assert r.classificar(ec="1075624862").lojista.cnpj14 == "22224579000109"
    assert r.classificar(ec="1043396662").lojista.nome_canonico == "Horizonte Viagens"


def test_resolves_by_cnpj_when_ec_unknown():
    assert _reg().classificar(ec="9", cnpj="78576234000179").lojista.cnpj14 == "78576234000179"


def test_resolves_by_exact_alias_only():
    r = _reg(aliases={"HORIZONTE VIAGENS TURISMO": "78576234000179"})
    assert r.classificar(nome="Horizonte  Viagens Turismo").lojista.cnpj14 == "78576234000179"
    assert r.classificar(nome="HORIZONTE VIAGEN").situacao == "NAO_RESOLVIDO"  # nunca "parecido"


def test_canonical_name_counts_as_exact_alias():
    assert _reg().classificar(nome="horizonte viagens").lojista.cnpj14 == "78576234000179"


def test_sem_contrato_ec_is_not_a_merchant():
    res = _reg().classificar(ec="1076801732")
    assert res.situacao == "SEM_CONTRATO" and res.lojista is None and res.nome == "Atlas Idiomas"


def test_unknown_everything_is_not_resolved():
    assert _reg().classificar(ec="1", cnpj="2", nome="x").situacao == "NAO_RESOLVIDO"


def test_ec_takes_priority_over_cnpj_and_alias():
    r = _reg()
    assert r.classificar(ec="1075624862", cnpj="78576234000179").lojista.cnpj14 == "22224579000109"


def test_inactive_status():
    assert _reg().por_cnpj("22348118000148").status == "INATIVO"
    assert _reg().por_cnpj("78576234000179").status == "ATIVO"


def test_same_ec_for_two_cnpjs_fails():
    with pytest.raises(ValueError, match="1075624862"):
        Registro.construir([_c("A", "11111111000111", "1075624862"), _c("B", "22222222000122", "1075624862")], {}, {})


def test_extra_ec_for_unknown_cnpj_fails():
    with pytest.raises(ValueError, match="99999999000199"):
        Registro.construir([_c("A", "11111111000111")], {"1": "99999999000199"}, {})


def test_alias_pointing_to_two_merchants_fails():
    cs = [_c("A Um", "11111111000111"), _c("B Dois", "22222222000122")]
    with pytest.raises(ValueError, match="a um"):
        Registro.construir(cs, {}, {}, aliases={"A UM": "22222222000122"})


def test_real_data_every_orbe_ec_is_classified(dados):
    from tarvo.config import carregar_defaults
    from tarvo.ingest.orbe import ler_orbe
    from tarvo.ingest.taxas import ler_taxas

    cfg = carregar_defaults()
    contratos, _ = ler_taxas(dados / "02_tabela_taxas_contratadas.xlsx")
    reg = Registro.construir(contratos, cfg.ecs_extra, cfg.sem_contrato, cfg.aliases)
    txs = ler_orbe(dados / "01_orbe_relatorio_comissoes_set2026.csv")
    sit = [reg.classificar(ec=t.cod_estabelecimento).situacao for t in txs]
    assert sit.count("NAO_RESOLVIDO") == 0
    assert sit.count("SEM_CONTRATO") == 57
    assert sit.count("LOJISTA") == 1943 - 57
