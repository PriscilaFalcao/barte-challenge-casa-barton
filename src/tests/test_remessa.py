import random
from datetime import date
from decimal import Decimal as D

import pytest

from tarvo.contracts.resolver import Resolvedor
from tarvo.core.excecoes import TipoExcecao
from tarvo.core.rastro import Rastro
from tarvo.engines.remessa import calcular_remessa
from tarvo.identity.registro import Registro
from tarvo.output.validators import validar_i_d1, validar_i_r1
from tests.helpers import CNPJ, contrato, op

ARQ = "03_email_ponte_cambio_relatorio_set2026.eml"


def _rodar(ops, contratos=None, mes="2026-09", **kw):
    contratos = contratos or [contrato()]  # spread em branco = padrão 1,5%
    reg = Registro.construir(contratos, {}, {})
    rastro = Rastro()
    res = calcular_remessa(ops, reg, Resolvedor(contratos), mes, rastro, **kw)
    return res, rastro


def test_commission_is_half_of_realized_spread_rounded_half_up():
    res, _ = _rodar([op(spread_brl="262.01")])
    assert res.comissoes[0]["comissao_brl"] == D("131.01")  # 131,005 -> 131,01 (exemplo do financeiro)


def test_row_shape_and_aggregation_per_merchant():
    res, _ = _rodar([op("PC-1", spread_brl="100.00"), op("PC-2", spread_brl="50.00")])
    (row,) = res.comissoes
    assert row["id_saida"] == f"COM-REM-{CNPJ}-202609"
    assert (row["cnpj"], row["lojista"], row["linha_negocio"], row["comissao_brl"]) == (CNPJ, "Loja Um", "REMESSA", D("75.00"))


def test_rastro_line_per_operation():
    _, r = _rodar([op("PC-1", spread_brl="100.00")])
    (l,) = [l for l in r.linhas() if l.id_saida.startswith("COM-REM")]
    assert (l.arquivo_origem, l.ref_origem, l.valor, l.componente, l.taxa_usada_pct, l.regra_id) == (
        ARQ, "PC-1", D("50.00"), "SPREAD", "50.00", "R1")


def test_ressalva_status_changes_nothing():
    res, _ = _rodar([op("PC-1", status="APROVADO C/ RESSALVA", spread_brl="100.00")])
    assert res.comissoes[0]["comissao_brl"] == D("50.00") and res.excecoes == []


def test_unknown_status_is_pending_and_excluded():
    res, r = _rodar([op("PC-1", spread_brl="100.00"), op("PC-2", status="REPROVADO", spread_brl="80.00")])
    assert res.comissoes[0]["comissao_brl"] == D("50.00")
    (e,) = res.excecoes
    assert (e.tipo, e.ref_origem, e.valor_brl) == (TipoExcecao.STATUS_PONTE_DESCONHECIDO, "PC-2", D("40.00"))
    assert r.soma(e.id_saida) == D("40.00")


def test_duplicate_counts_once_and_goes_to_ponte_list():
    a = op("PC-0162", spread_brl="821.88", linha=76)
    b = op("PC-0162", spread_brl="821.88", obs="reprocessada", linha=77)
    res, r = _rodar([a, b])
    assert res.comissoes[0]["comissao_brl"] == D("410.94")
    (e,) = res.excecoes
    assert (e.tipo, e.ref_origem, e.valor_brl, e.quem_decide) == (TipoExcecao.CONTESTACAO_PONTE, f"{CNPJ}-202609", D("410.94"), "Financeiro")
    assert r.soma(e.id_saida) == D("410.94") and "duplicada" in e.motivo and "PC-0162" in e.motivo
    assert len([l for l in r.linhas() if l.id_saida.startswith("COM-REM")]) == 1


def test_duplicate_with_different_values_says_so():
    a = op("PC-1", spread_brl="100.00", linha=6)
    b = op("PC-1", spread_brl="90.00", linha=7)
    res, _ = _rodar([a, b])
    assert res.comissoes[0]["comissao_brl"] == D("50.00")  # vale a primeira ocorrência
    assert "valores diferentes" in res.excecoes[0].motivo


def test_negative_spread_is_out_of_commission_and_only_a_contestation():
    """✅ V4: o lojista não pagou a mais, então não é divergência; é contestação pelo desvio contra o contrato."""
    neg = op("PC-N", me="1000.00", ptax="5.0000", spread_brl="-77.62", spread_pct="-0.015523",
             obs="Taxa travada no pedido (D-1)")
    res, r = _rodar([op("PC-1", spread_brl="100.00"), neg])
    assert res.comissoes[0]["comissao_brl"] == D("50.00")
    (pend,) = res.excecoes
    assert (pend.tipo, pend.ref_origem, pend.valor_brl) == (TipoExcecao.CONTESTACAO_PONTE, f"{CNPJ}-202609", D("-152.62"))
    assert res.divergencias == [] and r.soma(pend.id_saida) == D("-152.62")
    assert "Spread negativo" in pend.motivo and "PC-N" in pend.motivo


def test_negative_spread_divergence_can_be_switched_on():
    neg = op("PC-N", me="1000.00", ptax="5.0000", spread_brl="-77.62", spread_pct="-0.015523")
    res, _ = _rodar([neg], spread_negativo_em_divergencias=True)
    (d,) = res.divergencias
    assert (d["id_saida"], d["diferenca_brl"], d["taxa_contratada_pct"], d["taxa_aplicada_pct"]) == (
        "DIV-REM-PC-N", D("-152.62"), "1.50", "-1.5523")
    assert res.comissoes == []


def test_mundo_aberto_excess_is_commissioned_and_diverges_by_full_value():
    c = [contrato(spread="1.2")]
    mundo = op("PC-M", me="1000.00", ptax="5.0000", spread_brl="75.00", spread_pct="0.015")
    res, r = _rodar([mundo], c)
    assert res.comissoes[0]["comissao_brl"] == D("37.50")  # R4: a nota sai pelo realizado, com o excesso
    (d,) = res.divergencias
    assert d["diferenca_brl"] == D("15.00") and (d["taxa_contratada_pct"], d["taxa_aplicada_pct"]) == ("1.20", "1.50")
    (e,) = res.excecoes
    assert (e.tipo, e.ref_origem, e.valor_brl) == (TipoExcecao.CONTESTACAO_PONTE, f"{CNPJ}-202609", D("15.00"))
    assert d["natureza"] == "DIVERGENCIA_CONTRATO"
    assert next(l for l in r.linhas() if l.id_saida.startswith("COM-REM")).regra_id == "R4"


@pytest.mark.parametrize("pct,diverge", [("0.015016", False), ("0.0151", False), ("0.015101", True),
                                          ("0.0149", False), ("0.014899", True)])
def test_tolerance_is_one_hundredth_of_a_point_strictly_above(pct, diverge):
    res, _ = _rodar([op(spread_pct=pct)])
    assert bool(res.divergencias) is diverge


def test_blank_contract_means_standard_one_and_a_half_percent():
    res, _ = _rodar([op(spread_pct="0.015004")], [contrato(spread=None)])
    assert res.divergencias == []


def test_contract_picked_by_contratacao_date():
    c = [contrato(fim=date(2026, 9, 14), spread="1.2", ref="Taxas!L6"),
         contrato(ini=date(2026, 9, 15), spread="1.5", ref="Taxas!L7")]
    res, _ = _rodar([op("PC-1", dia=date(2026, 9, 10)), op("PC-2", dia=date(2026, 9, 20))], c)
    assert [d["ref_origem"] for d in res.divergencias] == ["PC-1"]


def test_missing_contract_keeps_commission_and_flags_the_operation():
    res, r = _rodar([op("PC-1", dia=date(2026, 9, 10), spread_brl="100.00")], [contrato(ini=date(2026, 9, 20))])
    assert res.comissoes[0]["comissao_brl"] == D("50.00") and res.divergencias == []
    (e,) = res.excecoes
    assert (e.tipo, e.ref_origem, e.valor_brl) == (TipoExcecao.CONTRATO_AMBIGUO, "PC-1", D("0.00"))
    assert r.soma(e.id_saida) == D("0.00")


def test_unresolved_cnpj_is_commissioned_and_pending_for_comercial():
    """✅ Desbravadores: a Ponte paga, então a comissão e a nota contam; cadastro vira pendência do comercial."""
    res, r = _rodar([op("PC-1", cnpj="99999999000199", spread_brl="100.00", spread_pct="0.03")])
    (c,) = res.comissoes
    assert (c["cnpj"], c["lojista"], c["comissao_brl"]) == ("99999999000199", "CLIENTE", D("50.00"))
    assert res.divergencias == []  # sem contrato, a divergência não é avaliada
    (e,) = res.excecoes
    assert (e.tipo, e.ref_origem, e.valor_brl, e.quem_decide) == (
        TipoExcecao.ENTIDADE_NAO_RESOLVIDA, "99999999000199", D("50.00"), "Comercial")
    assert r.soma(e.id_saida) == D("50.00") and r.soma(c["id_saida"]) == D("50.00")


def test_competencia_is_contratacao_date():
    ops = [op("PC-1", dia=date(2026, 9, 30)), op("PC-2", dia=date(2026, 10, 1)), op("PC-3", dia=date(2026, 8, 31))]
    ops[0] = ops[0].__class__(**{**ops[0].__dict__, "data_liquidacao": date(2026, 10, 1)})  # liquida em outubro
    res, _ = _rodar(ops)
    assert res.comissoes[0]["comissao_brl"] == D("37.50")


def test_order_independent_and_invariants_hold():
    ops = [op(f"PC-{i:03d}", spread_brl=f"{100 + i}.37", spread_pct="0.0151" if i % 7 else "0.0170", linha=6 + i)
           for i in range(30)]
    a, ra = _rodar(ops)
    emb = ops[:]
    random.Random(5).shuffle(emb)
    b, _ = _rodar(emb)
    assert a.comissoes == b.comissoes and a.divergencias == b.divergencias
    assert [e.id_saida for e in a.excecoes] == [e.id_saida for e in b.excecoes]
    pend = [{"id_saida": e.id_saida, "valor_brl": e.valor_brl} for e in a.excecoes]
    validar_i_r1({"comissoes_por_lojista": a.comissoes, "divergencias_taxa": a.divergencias, "pendencias": pend}, ra)
    validar_i_d1(a.divergencias)


def test_everything_to_contest_for_one_merchant_is_one_pending():
    c = [contrato(spread="1.2")]
    a = op("PC-M", spread_brl="75.00", spread_pct="0.015", linha=6)
    b = op("PC-M", spread_brl="75.00", spread_pct="0.015", obs="reprocessada", linha=7)
    res, r = _rodar([a, b], c)
    (e,) = res.excecoes
    assert (e.tipo, e.ref_origem) == (TipoExcecao.CONTESTACAO_PONTE, f"{CNPJ}-202609")
    assert e.valor_brl == D("15.00") + D("37.50")  # excesso + comissão inflada da repetição
    assert "duplicada" in e.motivo and "Excesso de spread" in e.motivo
    assert r.soma(e.id_saida) == e.valor_brl
    assert res.comissoes[0]["comissao_brl"] == D("37.50")


def test_duplicated_negative_operation_is_one_merged_pending():
    a = op("PC-N", spread_brl="-77.62", spread_pct="-0.015523", linha=6)
    b = op("PC-N", spread_brl="-77.62", spread_pct="-0.015523", linha=7)
    res, r = _rodar([a, b])
    (e,) = res.excecoes
    assert e.valor_brl == D("-152.62") + D("-38.81") and r.soma(e.id_saida) == e.valor_brl
    assert "negativo" in e.motivo and "duplicada" in e.motivo


def test_one_contestation_per_merchant_even_with_many_overlaps():
    cnpjs = [f"{i:02d}111111000111" for i in range(3)]
    c = [contrato(cnpj=x, ec=f"10000000{i:02d}", spread="1.2", nome=f"Loja {i}") for i, x in enumerate(cnpjs)]
    ops = []
    for i in range(10):
        n, cnpj = f"PC-{i}", cnpjs[i % 3]
        neg = i % 4 == 0
        kw = dict(cnpj=cnpj, spread_brl="-77.00" if neg else "75.00", spread_pct="-0.0155" if neg else "0.015")
        ops += [op(n, linha=2 * i + 6, **kw), op(n, linha=2 * i + 7, **kw)]
    res, r = _rodar(ops, c)
    assert sorted(e.ref_origem for e in res.excecoes) == sorted(f"{x}-202609" for x in cnpjs)
    for e in res.excecoes:
        assert r.soma(e.id_saida) == e.valor_brl


def test_out_of_month_operations_are_counted_in_the_ledger():
    from tarvo.core.ledger import Ledger

    contratos = [contrato()]
    ledger = Ledger()
    calcular_remessa([op("PC-1", dia=date(2026, 10, 1)), op("PC-2", dia=date(2026, 9, 30))],
                     Registro.construir(contratos, {}, {}), Resolvedor(contratos), "2026-09", Rastro(),
                     ledger=ledger)
    assert ledger.contar("Ponte", "fora do mês") == 1
