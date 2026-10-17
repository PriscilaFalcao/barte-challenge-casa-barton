"""B5 com o data pack real: notas de setembro. Fecha o nível Alvo de comissões e notas."""
from decimal import Decimal as D

import pytest

from tarvo.config import carregar_defaults
from tarvo.contracts.resolver import Resolvedor
from tarvo.core.excecoes import TipoExcecao
from tarvo.core.rastro import Rastro
from tarvo.engines.checkout import calcular_checkout
from tarvo.engines.notas import PONTE_CNPJ, calcular_notas
from tarvo.engines.remessa import calcular_remessa
from tarvo.identity.registro import Registro
from tarvo.ingest.orbe import ler_orbe
from tarvo.ingest.ponte import ler_ponte
from tarvo.ingest.taxas import ler_taxas
from tarvo.output.validators import validar_i_n1, validar_i_r1

CASA = "00520815000100"


@pytest.fixture(scope="module")
def corrida(dados):
    cfg = carregar_defaults()
    contratos, _ = ler_taxas(dados / "02_tabela_taxas_contratadas.xlsx")
    reg = Registro.construir(contratos, cfg.ecs_extra, cfg.sem_contrato, cfg.aliases)
    rs = Resolvedor(contratos, cfg.overrides)
    rastro = Rastro()
    chk = calcular_checkout(ler_orbe(dados / "01_orbe_relatorio_comissoes_set2026.csv"), reg, rs, "2026-09", rastro)
    rem = calcular_remessa(ler_ponte(dados / "03_email_ponte_cambio_relatorio_set2026.eml"), reg, rs, "2026-09", rastro)
    comissoes = chk.comissoes + rem.comissoes
    return comissoes, calcular_notas(comissoes, rastro, "2026-09"), rastro


def test_twenty_checkout_notes_and_one_remessa_note(corrida):
    _, res, _ = corrida
    chk = [n for n in res.notas if n["linha_negocio"] == "CHECKOUT"]
    rem = [n for n in res.notas if n["linha_negocio"] == "REMESSA"]
    assert (len(chk), len(rem)) == (20, 1)


def test_casa_has_no_checkout_note_and_a_pending_for_helena(corrida):
    _, res, _ = corrida
    assert all(n["tomador_cnpj"] != CASA for n in res.notas)  # a remessa da Casa vai na nota da Ponte
    (e,) = [e for e in res.excecoes if e.tipo == TipoExcecao.COMISSAO_NAO_POSITIVA]
    assert (e.tipo, e.valor_brl, e.quem_decide) == (TipoExcecao.COMISSAO_NAO_POSITIVA, D("-5.50"), "Financeiro")
    assert e.ref_origem == f"{CASA}-202609"


def test_atlas_has_no_note(corrida):
    _, res, _ = corrida
    assert all("Atlas" not in n["tomador"] and n["tomador_cnpj"] != "39566044000119" for n in res.notas)


def test_remessa_note_is_39543_45_to_ponte_cambio(corrida):
    _, res, _ = corrida
    (n,) = [n for n in res.notas if n["linha_negocio"] == "REMESSA"]
    assert (n["id_saida"], n["tomador_cnpj"], n["valor_brl"]) == ("NF-REM-202609", PONTE_CNPJ, D("39543.45"))


def test_every_checkout_note_equals_that_merchants_commission(corrida):
    comissoes, res, _ = corrida
    por_cnpj = {c["cnpj"]: c["comissao_brl"] for c in comissoes if c["linha_negocio"] == "CHECKOUT"}
    for n in res.notas:
        if n["linha_negocio"] == "CHECKOUT":
            assert n["valor_brl"] == por_cnpj[n["tomador_cnpj"]]


def test_notes_total_is_positive_commissions_only(corrida):
    comissoes, res, _ = corrida
    positivas = sum(c["comissao_brl"] for c in comissoes if c["linha_negocio"] == "CHECKOUT" and c["comissao_brl"] > 0)
    assert sum(n["valor_brl"] for n in res.notas) == positivas + D("39543.45") == D("246588.68")


def test_note_rastro_reconciles_and_invariants_hold(corrida):
    comissoes, res, rastro = corrida
    pend = [{"id_saida": e.id_saida, "valor_brl": e.valor_brl} for e in res.excecoes]
    validar_i_r1({"comissoes_por_lojista": comissoes, "notas_a_emitir": res.notas, "pendencias": pend}, rastro)
    validar_i_n1(res.notas)
