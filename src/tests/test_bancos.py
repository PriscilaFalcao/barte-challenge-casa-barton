"""Motor de classificação bancária (B6) com lançamentos sintéticos."""
import re
from datetime import date
from decimal import Decimal as D

import pytest

from tarvo.config import AlertaLancamento, RegraLancamento
from tarvo.core.excecoes import TipoExcecao
from tarvo.core.rastro import Rastro
from tarvo.engines.bancos import classificar_lancamentos
from tarvo.ingest.erros import LayoutError
from tarvo.ingest.extrato import Lancamento
from tarvo.ingest.plano_contas import Conta
from tarvo.output.validators import ValidationError, validar_i_c1, validar_i_r1
from tests.helpers import op

PLANO = {c: Conta(c, c, analitica) for c, analitica in [
    ("1.1", False), ("1.1.09.001", True), ("1.1.09.002", True), ("1.1.03.003", True), ("2.1.01.001", True),
    ("2.1.02.001", True), ("4.2.01", True), ("4.2.06", True)]}
PROV = {"credito": "1.1.09.002", "debito": "1.1.03.003"}


def regra(id_, banco, padrao, conta, sinal=None, pend=None, motivo=""):
    return RegraLancamento(id_, banco, re.compile(padrao), conta, sinal, "", pend, motivo)


REGRAS = (
    regra("AUR-CONTABIL", "AURORA", "^pix enviado contabilidade", "4.2.06", "debito"),
    regra("AUR-REPASSE", "AURORA", "^pix enviado ", "2.1.01.001", "debito"),
    regra("AUR-PIX-SEM-ID", "AURORA", "^pix recebido .*sem identificacao", "1.1.09.002", "credito",
          TipoExcecao.LANCAMENTO_SEM_ORIGEM, "PIX de R$ {valor} em {data} ({ref})"),
    regra("AUR-TRANSF-MER", "AURORA", "^transf entre contas", "1.1.09.001", "debito"),
    regra("MER-TED-TARVO", "MERIDIANO", "^ted recebida tarvo", "1.1.09.001", "credito"),
    regra("MER-TED-PONTE", "MERIDIANO", "^ted enviada ponte", "2.1.02.001", "debito"),
    regra("MER-TARIFA", "MERIDIANO", "^tarifa ", "4.2.01", "debito"),
)


def lan(ref, desc, valor, dia=date(2026, 9, 10), banco="AURORA"):
    return Lancamento(banco, ref, dia, desc, D(valor), f"{banco}.arq")


def rodar(lans, regras=REGRAS, alertas=(), ops=(), mes="2026-09"):
    rastro = Rastro()
    res = classificar_lancamentos(lans, PLANO, regras, PROV, alertas, list(ops), mes, rastro)
    return res, rastro


def por_ref(res):
    return {l["ref_origem"]: l for l in res.lancamentos}


def test_first_matching_rule_wins_so_specific_comes_before_generic():
    res, _ = rodar([lan("L1", "PIX ENVIADO CONTABILIDADE EXATA LTDA", "-6800.00"),
                    lan("L2", "PIX ENVIADO ROTA GLOBAL INTERCAMBIO LT", "-100.00")])
    r = por_ref(res)
    assert (r["L1"]["conta_codigo"], r["L1"]["regra_id"]) == ("4.2.06", "AUR-CONTABIL")
    assert (r["L2"]["conta_codigo"], r["L2"]["metodo"], r["L2"]["confianca"]) == ("2.1.01.001", "REGRA", D("1.00"))


def test_match_ignores_case_and_accents_and_respects_bank():
    res, _ = rodar([lan("M1", "Tarifa Manutenção", "-1.00", banco="MERIDIANO"), lan("L1", "TARIFA X", "-1.00")])
    r = por_ref(res)
    assert r["M1"]["conta_codigo"] == "4.2.01"
    assert r["L1"]["metodo"] == "HUMANO"  # a regra de tarifa é do Meridiano


def test_sign_mismatch_does_not_match():
    res, _ = rodar([lan("L1", "PIX ENVIADO ESTORNO", "50.00")])  # crédito com cara de saída
    assert por_ref(res)["L1"]["metodo"] == "HUMANO"


def test_no_rule_goes_to_provisional_account_by_sign_with_pending():
    res, rastro = rodar([lan("L1", "ALGO NOVO", "10.00"), lan("L2", "OUTRA COISA", "-20.00")])
    r = por_ref(res)
    assert (r["L1"]["conta_codigo"], r["L1"]["metodo"], r["L1"]["confianca"]) == ("1.1.09.002", "HUMANO", D("0.00"))
    assert r["L2"]["conta_codigo"] == "1.1.03.003"
    assert [(e.tipo, e.ref_origem, e.valor_brl) for e in res.excecoes] == [
        (TipoExcecao.CLASSIFICACAO_BAIXA_CONFIANCA, "L1", D("10.00")),
        (TipoExcecao.CLASSIFICACAO_BAIXA_CONFIANCA, "L2", D("-20.00"))]
    assert "ALGO NOVO" in res.excecoes[0].motivo and rastro.soma(res.excecoes[1].id_saida) == D("-20.00")


def test_rule_with_pending_classifies_by_rule_and_opens_pending():
    res, rastro = rodar([lan("L50", "PIX RECEBIDO 38686002000180 SEM IDENTIFICACAO", "7350.00", date(2026, 9, 16))])
    l = por_ref(res)["L50"]
    assert (l["conta_codigo"], l["metodo"], l["confianca"]) == ("1.1.09.002", "REGRA", D("1.00"))
    (e,) = res.excecoes
    assert (e.tipo, e.id_saida, e.valor_brl) == (TipoExcecao.LANCAMENTO_SEM_ORIGEM, "PEN-LANCAMENTO_SEM_ORIGEM-L50", D("7350.00"))
    assert e.motivo == "PIX de R$ 7350.00 em 16/09/2026 (L50)"
    assert rastro.soma(e.id_saida) == D("7350.00")


def test_rows_and_rastro_reconcile_and_ids_follow_prd():
    res, rastro = rodar([lan("L9", "PIX ENVIADO X", "-1.00"), lan("MRD1", "TARIFA Y", "-2.00", banco="MERIDIANO")])
    assert sorted(l["id_saida"] for l in res.lancamentos) == ["LAN-AUR-L9", "LAN-MER-MRD1"]
    validar_i_r1({"lancamentos_classificados": res.lancamentos}, rastro)
    validar_i_c1(res.lancamentos, PLANO)


def test_ted_to_ponte_reconciles_with_operations_of_the_day():
    dia = date(2026, 9, 10)
    ops = [op("PC-1", dia=dia), op("PC-2", dia=dia), op("PC-2", dia=dia, linha=7), op("PC-3", dia=date(2026, 9, 11))]
    ops = [o.__class__(**{**o.__dict__, "valor_brl": D("1000.00"), "iof": D("3.80")}) for o in ops]
    res, _ = rodar([lan("M1", "TED ENVIADA PONTE CAMBIO SA LIQ OPERACOES", "-2007.60", dia, "MERIDIANO")], ops=ops)
    assert res.conciliadas == 1  # a duplicata PC-2 conta uma vez
    # sem PIX de lojista no mês, a TED liquida recursos de antes: só a conferência do saldo, sem outra pendência
    assert [e.ref_origem for e in res.excecoes] == ["RECURSOS-REMESSAS-202609"]


def test_ted_to_ponte_that_does_not_match_is_pending():
    res, _ = rodar([lan("M1", "TED ENVIADA PONTE CAMBIO SA LIQ OPERACOES", "-50.00", banco="MERIDIANO")])
    (e,) = [e for e in res.excecoes if e.tipo == TipoExcecao.LANCAMENTO_SEM_ORIGEM]
    assert "não bate" in e.motivo
    assert por_ref(res)["M1"]["conta_codigo"] == "2.1.02.001"


def test_transfers_pair_by_value_and_unpaired_outflow_is_checked_next_month():
    lans = [lan("L12", "TRANSF ENTRE CONTAS P/ BCO MERIDIANO", "-350000.00", date(2026, 9, 2)),
            lan("L92", "TRANSF ENTRE CONTAS P/ BCO MERIDIANO", "-300000.00", date(2026, 9, 30)),
            lan("M7", "TED RECEBIDA TARVO PAGAMENTOS LTDA - MESMA TITULARIDADE", "350000.00", date(2026, 9, 2), "MERIDIANO")]
    res, _ = rodar(lans)
    (e,) = res.excecoes
    assert (e.tipo, e.ref_origem, e.valor_brl, e.quem_decide) == (
        TipoExcecao.CONFERIR_MES_SEGUINTE, "L92", D("-300000.00"), "Financeiro")
    assert por_ref(res)["L92"]["conta_codigo"] == "1.1.09.001"


def test_unpaired_inflow_is_pending():
    res, _ = rodar([lan("M7", "TED RECEBIDA TARVO - MESMA TITULARIDADE", "300000.00", date(2026, 10, 1), "MERIDIANO")],
                   mes="2026-10")
    (e,) = res.excecoes
    assert e.tipo == TipoExcecao.LANCAMENTO_SEM_ORIGEM and "mês anterior" in e.motivo


def test_alert_adds_pending_without_changing_the_account():
    a = AlertaLancamento("2026-09", "AURORA", "L34", date(2026, 9, 10), D("-112220.15"),
                         TipoExcecao.REPASSE_ATIPICO, "repasse atípico")
    res, rastro = rodar([lan("L34", "PIX ENVIADO ATLAS IDIOMAS LTDA", "-112220.15")], alertas=(a,))
    assert por_ref(res)["L34"]["conta_codigo"] == "2.1.01.001"
    (e,) = res.excecoes
    assert (e.tipo, e.ref_origem, e.valor_brl, e.motivo) == (TipoExcecao.REPASSE_ATIPICO, "L34", D("-112220.15"), "repasse atípico")
    assert rastro.soma(e.id_saida) == D("-112220.15")


def test_alert_of_another_month_is_inert():
    a = AlertaLancamento("2026-09", "AURORA", "L34", date(2026, 9, 10), D("-112220.15"), TipoExcecao.REPASSE_ATIPICO, "x")
    res, _ = rodar([lan("L34", "PIX ENVIADO OUTRO", "-5.00", date(2026, 10, 10))], alertas=(a,), mes="2026-10")
    assert res.excecoes == []


def test_alert_that_does_not_match_the_statement_fails():
    a = AlertaLancamento("2026-09", "AURORA", "L34", date(2026, 9, 10), D("-112220.15"), TipoExcecao.REPASSE_ATIPICO, "x")
    with pytest.raises(LayoutError, match="L34"):
        rodar([lan("L34", "PIX ENVIADO OUTRO", "-5.00")], alertas=(a,))


def test_rule_pointing_to_synthetic_or_missing_account_fails_before_classifying():
    for conta in ("1.1", "9.9.99"):
        with pytest.raises(LayoutError, match=conta):
            rodar([], regras=(regra("X", "AURORA", "^x", conta),))


def test_out_of_month_lines_are_left_out():
    res, _ = rodar([lan("L1", "PIX ENVIADO X", "-1.00", date(2026, 8, 31))])
    assert res.lancamentos == []


def test_i_c1_rejects_synthetic_account():
    with pytest.raises(ValidationError, match="I-C1"):
        validar_i_c1([{"id_saida": "LAN-AUR-L1", "conta_codigo": "1.1"}], PLANO)


def test_pix_surplus_over_teds_points_to_the_single_pix_that_explains_it():
    regras = REGRAS + (regra("MER-PIX-LOJISTA", "MERIDIANO", "^pix receb ", "2.1.02.001", "credito"),)
    dia = date(2026, 9, 10)
    o = op("PC-1", dia=dia)
    ops = [o.__class__(**{**o.__dict__, "valor_brl": D("1000.00"), "iof": D("3.80")})]
    res, rastro = rodar([lan("M1", "PIX RECEB LOJA A", "1003.80", dia, "MERIDIANO"),
                         lan("M2", "TED ENVIADA PONTE CAMBIO SA LIQ OPERACOES", "-1003.80", dia, "MERIDIANO"),
                         lan("M3", "PIX RECEB LOJA B", "18240.00", dia, "MERIDIANO")], regras=regras, ops=ops)
    (e,) = res.excecoes
    assert (e.tipo, e.ref_origem, e.valor_brl, e.quem_decide) == (
        TipoExcecao.CONFERIR_MES_SEGUINTE, "M3", D("18240.00"), "Financeiro")
    assert rastro.soma(e.id_saida) == D("18240.00")


def test_pix_surplus_without_a_single_match_is_checked_as_a_set():
    regras = REGRAS + (regra("MER-PIX-LOJISTA", "MERIDIANO", "^pix receb ", "2.1.02.001", "credito"),)
    res, rastro = rodar([lan("M1", "PIX RECEB LOJA A", "100.00", banco="MERIDIANO"),
                         lan("M2", "PIX RECEB LOJA B", "50.00", banco="MERIDIANO")], regras=regras)
    (e,) = res.excecoes
    assert (e.ref_origem, e.valor_brl) == ("RECURSOS-REMESSAS-202609", D("150.00"))
    assert rastro.soma(e.id_saida) == D("150.00")
