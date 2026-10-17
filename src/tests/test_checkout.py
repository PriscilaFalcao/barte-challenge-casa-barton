import random
from datetime import date
from decimal import Decimal as D

import pytest

from tarvo.config import OverrideTaxa
from tarvo.contracts.resolver import Resolvedor
from tarvo.core.excecoes import TipoExcecao
from tarvo.core.rastro import Rastro
from tarvo.engines.checkout import calcular_checkout
from tarvo.identity.registro import Registro
from tarvo.ingest.orbe import OrbeTx
from tarvo.ingest.taxas import ContratoLinha
from tarvo.output.validators import validar_i_r1

from tests.helpers import CNPJ, EC, contrato as _contrato, rodar_checkout as _rodar, tx as _tx


def test_venda_commission_is_gross_times_contracted_rate_not_orbe_fee():
    res, _ = _rodar([_tx(bruto="1000.00", valor_taxa="999.99")])  # débito 1,00%
    assert res.comissoes[0]["comissao_brl"] == D("10.00")


def test_rounding_happens_per_line_before_summing():
    # 0,50 x 1% = 0,005 -> 0,01 em cada linha; somar antes e arredondar daria 0,01
    txs = [_tx("TX1", bruto="0.50"), _tx("TX2", bruto="0.50")]
    res, _ = _rodar(txs)
    assert res.comissoes[0]["comissao_brl"] == D("0.02")


def test_estorno_is_negative_and_rounds_symmetrically():
    res, _ = _rodar([_tx("TX1", tipo="ESTORNO", bruto="-0.50", ref="TX0", orig=date(2026, 9, 1))])
    assert res.comissoes[0]["comissao_brl"] == D("-0.01")


def test_estorno_uses_rate_valid_on_original_sale_date():
    contratos = [_contrato(fim=date(2026, 9, 14), debito="1.00", ref="Taxas!L6"),
                 _contrato(ini=date(2026, 9, 15), debito="2.00", ref="Taxas!L7")]
    res, r = _rodar([_tx("TX1", dia=date(2026, 9, 20), tipo="ESTORNO", bruto="-1000.00",
                         ref="TX0", orig=date(2026, 9, 10))], contratos)
    assert res.comissoes[0]["comissao_brl"] == D("-10.00")
    (linha,) = r.linhas()
    assert linha.taxa_usada_pct == "1.00" and linha.regra_id == "C3"


def test_estorno_of_previous_month_sale_is_tagged_historico():
    _, r = _rodar([_tx("TX1", tipo="ESTORNO", bruto="-100.00", ref="TX0", orig=date(2026, 8, 21))])
    assert r.linhas()[0].regra_id == "C3-HISTORICO"


def test_antecipacao_uses_antecipation_rate_and_own_component():
    res, r = _rodar([_tx("AN1", tipo="ANTECIPACAO", mod="", parc=None, bruto="10000.00")])
    assert res.comissoes[0]["comissao_brl"] == D("200.00")
    (l,) = r.linhas()
    assert (l.componente, l.regra_id, l.taxa_usada_pct) == ("ANTECIPACAO", "C4", "2.00")


def test_reversao_cancels_exactly_the_antecipation_commission():
    txs = [_tx("AN1", tipo="ANTECIPACAO", mod="", parc=None, bruto="52314.21"),
           _tx("AN2", dia=date(2026, 9, 5), tipo="REVERSAO_ANTECIPACAO", mod="", parc=None,
               bruto="-52314.21", ref="AN1", orig=date(2026, 9, 10))]
    res, _ = _rodar(txs)
    assert res.comissoes[0]["comissao_brl"] == D("0.00")


def test_sale_and_antecipation_of_same_merchant_go_in_one_row_with_components_in_rastro():
    txs = [_tx("TX1", bruto="1000.00"), _tx("AN1", tipo="ANTECIPACAO", mod="", parc=None, bruto="1000.00")]
    res, r = _rodar(txs)
    assert len(res.comissoes) == 1 and res.comissoes[0]["comissao_brl"] == D("30.00")
    assert {l.componente for l in r.linhas()} == {"MDR", "ANTECIPACAO"}


def test_row_shape_and_id():
    res, _ = _rodar([_tx()])
    row = res.comissoes[0]
    assert row["id_saida"] == f"COM-CHK-{CNPJ}-202609"
    assert (row["cnpj"], row["lojista"], row["linha_negocio"]) == (CNPJ, "Loja Um", "CHECKOUT")


def test_two_ecs_of_the_same_merchant_aggregate():
    txs = [_tx("TX1", ec=EC), _tx("TX2", ec="1000000002")]
    res, _ = _rodar(txs, ecs_extra={"1000000002": CNPJ})
    assert len(res.comissoes) == 1 and res.comissoes[0]["comissao_brl"] == D("2.00")


def test_rastro_sums_match_and_validator_passes():
    txs = [_tx("TX1", bruto="123.45"), _tx("TX2", bruto="0.50"), _tx("TX3", tipo="ESTORNO", bruto="-50.00", ref="X", orig=date(2026, 9, 1))]
    res, r = _rodar(txs)
    validar_i_r1({"comissoes_por_lojista": res.comissoes}, r)
    assert {l.ref_origem for l in r.linhas()} == {"TX1", "TX2", "TX3"}
    assert all(l.arquivo_origem == "01_orbe_relatorio_comissoes_set2026.csv" for l in r.linhas())


def test_zero_commission_line_still_has_rastro():
    ovr = OverrideTaxa(CNPJ, ("DEBITO",), D("0"), date(2026, 9, 1), date(2026, 12, 31), "C8", "Slack")
    res, r = _rodar([_tx("TX1", bruto="500.00")], overrides=[ovr])
    assert res.comissoes[0]["comissao_brl"] == D("0.00")
    (l,) = r.linhas()
    assert (l.ref_origem, l.valor, l.regra_id) == ("TX1", D("0.00"), "C8")


def test_negative_total_is_reported_not_dropped():
    ovr = OverrideTaxa(CNPJ, ("DEBITO",), D("0"), date(2026, 9, 1), date(2026, 12, 31), "C8", "Slack")
    res, _ = _rodar([_tx("TX1", tipo="ESTORNO", bruto="-367.00", ref="X", orig=date(2026, 8, 21))],
                    [_contrato(debito="1.50")], overrides=[ovr])
    assert res.comissoes[0]["comissao_brl"] == D("-5.51")  # estorno de agosto, antes do override


def test_sem_contrato_is_not_commissioned_and_becomes_pending_with_rastro():
    atlas = [_tx("TX7", ec="777", bruto="100.00", valor_taxa="2.00"),
             _tx("TX8", ec="777", tipo="ESTORNO", bruto="-10.00", valor_taxa="-0.20", ref="TX7", orig=date(2026, 9, 10))]
    res, r = _rodar(atlas, sem_contrato={"777": "Atlas"})
    assert res.comissoes == []
    (e,) = res.excecoes
    assert (e.tipo, e.ref_origem, e.valor_brl, e.quem_decide) == (TipoExcecao.SEM_CONTRATO, "777", D("1.80"), "Diego")
    assert r.soma(e.id_saida) == D("1.80")


def test_unresolved_entity_is_pending_not_commissioned():
    res, r = _rodar([_tx("TX9", ec="555", valor_taxa="3.00")])
    assert res.comissoes == []
    (e,) = res.excecoes
    assert (e.tipo, e.ref_origem) == (TipoExcecao.ENTIDADE_NAO_RESOLVIDA, "555")
    assert r.soma(e.id_saida) == e.valor_brl == D("3.00")


def test_contract_error_makes_line_a_pending_and_excludes_it():
    txs = [_tx("TX1", bruto="1000.00"),
           _tx("TX2", mod="CREDITO PARCELADO", parc=13, bruto="500.00", valor_taxa="4.00")]
    res, r = _rodar(txs)
    assert res.comissoes[0]["comissao_brl"] == D("10.00")
    (e,) = res.excecoes
    assert e.tipo == TipoExcecao.CONTRATO_AMBIGUO and e.ref_origem == "TX2" and "13x" in e.motivo
    assert r.soma(e.id_saida) == D("4.00")


def test_other_months_are_ignored():
    res, r = _rodar([_tx("TX1", dia=date(2026, 8, 31)), _tx("TX2", dia=date(2026, 10, 1))])
    assert res.comissoes == [] and r.linhas() == []


def test_result_is_independent_of_input_order():
    txs = [_tx(f"TX{i}", bruto=f"{100 + i}.37") for i in range(30)]
    a, ra = _rodar(txs)
    shuffled = txs[:]
    random.Random(7).shuffle(shuffled)
    b, rb = _rodar(shuffled)
    assert a.comissoes == b.comissoes
    assert sorted(ra.linhas(), key=lambda l: l.ref_origem) == sorted(rb.linhas(), key=lambda l: l.ref_origem)


def test_calculation_lines_expose_detail_for_divergences():
    res, _ = _rodar([_tx("TX1", bruto="1000.00", aplicada="1.20")])
    (l,) = res.linhas
    assert (l.tx.id_transacao, l.cnpj14, l.produto, l.taxa.pct, l.comissao) == ("TX1", CNPJ, "DEBITO", D("1.00"), D("10.00"))


def test_out_of_month_lines_are_counted_in_the_ledger():
    from tarvo.core.ledger import Ledger
    from tarvo.engines.checkout import calcular_checkout
    from tarvo.contracts.resolver import Resolvedor
    from tarvo.core.rastro import Rastro
    from tarvo.identity.registro import Registro

    contratos = [_contrato()]
    ledger = Ledger()
    calcular_checkout([_tx("TX1", dia=date(2026, 8, 31)), _tx("TX2", dia=date(2026, 10, 1)), _tx("TX3")],
                      Registro.construir(contratos, {}, {}), Resolvedor(contratos), "2026-09", Rastro(), ledger)
    assert ledger.contar("Orbe", "fora do mês") == 2
