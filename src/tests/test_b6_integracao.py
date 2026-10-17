"""B6 com o data pack real: classificação dos dois extratos (HIPOTESES 2.5)."""
import collections
from decimal import Decimal as D

import pytest

from tarvo.config import carregar_defaults
from tarvo.core.excecoes import TipoExcecao
from tarvo.core.rastro import Rastro
from tarvo.engines.bancos import classificar_lancamentos
from tarvo.ingest.aurora import ler_aurora
from tarvo.ingest.meridiano import ler_meridiano
from tarvo.ingest.plano_contas import ler_plano_contas
from tarvo.ingest.ponte import ler_ponte
from tarvo.output.validators import validar_i_c1, validar_i_r1


@pytest.fixture(scope="module")
def corrida(dados):
    cfg = carregar_defaults()
    plano = ler_plano_contas(dados / "04_plano_de_contas_fenix_erp.csv")
    lans = (ler_aurora(dados / "05a_extrato_banco_aurora_cc4471_set2026.csv").lancamentos
            + ler_meridiano(dados / "05b_extrato_banco_meridiano_cc90233_set2026.ofx").lancamentos)
    ops = ler_ponte(dados / "03_email_ponte_cambio_relatorio_set2026.eml")
    rastro = Rastro()
    res = classificar_lancamentos(lans, plano, cfg.regras_lancamento, cfg.conta_provisoria,
                                  cfg.alertas_lancamento, ops, "2026-09", rastro)
    return res, rastro, plano


def _conta(res, ref):
    return next(l["conta_codigo"] for l in res.lancamentos if l["ref_origem"] == ref)


def test_every_line_is_classified_by_rule(corrida):
    res, _, _ = corrida
    assert len(res.lancamentos) == 184
    assert collections.Counter(l["banco"] for l in res.lancamentos) == {"AURORA": 84, "MERIDIANO": 100}
    assert {(l["metodo"], l["confianca"]) for l in res.lancamentos} == {("REGRA", D("1.00"))}


@pytest.mark.parametrize("ref,conta", [
    ("L9", "1.1.03.001"),    # TED Orbe
    ("L12", "1.1.09.001"),   # transferência para o Meridiano
    ("L15", "2.1.04.001"),   # folha 08/2026: baixa a provisão
    ("L42", "2.1.03.003"), ("L54", "2.1.04.002"), ("L55", "2.1.04.003"),
    ("L57", "2.1.03.004"), ("L86", "2.1.03.001"), ("L87", "2.1.03.002"),
    ("L16", "4.2.02"), ("L47", "4.2.03"), ("L48", "4.2.04"), ("L53", "4.2.06"), ("L10", "4.2.01"),
    ("L18", "2.1.01.001"), ("L34", "2.1.01.001"),  # repasse à Atlas segue normal
    ("L50", "1.1.09.002"), ("L65", "2.1.01.001"),
    ("MRD2026090003", "2.1.02.001"), ("MRD2026090425", "2.1.02.001"), ("MRD2026090094", "2.1.02.001"),
    ("MRD2026090132", "1.1.03.002"), ("MRD2026090107", "1.1.09.001"), ("MRD2026090143", "1.1.02.001"),
    ("MRD2026090254", "1.1.02.001"), ("MRD2026090680", "3.2.01"), ("MRD2026090586", "4.3.01"),
    ("MRD2026090696", "4.2.01"), ("MRD2026090103", "4.2.01"), ("MRD2026090292", "4.2.05"),
])
def test_known_lines_get_the_documented_account(corrida, ref, conta):
    res, _, _ = corrida
    assert _conta(res, ref) == conta


def test_all_21_teds_to_ponte_match_the_operations_of_the_day(corrida):
    res, _, _ = corrida
    assert res.conciliadas == 21


def test_bank_pendings_are_the_five_known_cases(corrida):
    res, rastro, _ = corrida
    assert {(e.tipo, e.ref_origem): e.valor_brl for e in res.excecoes} == {
        (TipoExcecao.LANCAMENTO_SEM_ORIGEM, "L50"): D("7350.00"),
        (TipoExcecao.DEVOLUCAO_PIX, "L65"): D("12400.00"),
        (TipoExcecao.REPASSE_ATIPICO, "L34"): D("-112220.15"),
        (TipoExcecao.CONFERIR_MES_SEGUINTE, "L92"): D("-300000.00"),
        (TipoExcecao.CONFERIR_MES_SEGUINTE, "MRD2026090425"): D("18240.00"),
    }
    assert {e.quem_decide for e in res.excecoes} == {"Helena"}
    for e in res.excecoes:
        assert rastro.soma(e.id_saida) == e.valor_brl


def test_invariants(corrida):
    res, rastro, plano = corrida
    pend = [{"id_saida": e.id_saida, "valor_brl": e.valor_brl} for e in res.excecoes]
    validar_i_r1({"lancamentos_classificados": res.lancamentos, "pendencias": pend}, rastro)
    validar_i_c1(res.lancamentos, plano)
