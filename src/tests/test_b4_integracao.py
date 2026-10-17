"""B4 com o data pack real. Números ✅ de HIPOTESES.md (Lucca: 39.543,45 e 3.565,98)."""
import collections
from decimal import Decimal as D

import pytest

from tarvo.config import carregar_defaults
from tarvo.contracts.resolver import Resolvedor
from tarvo.core.excecoes import TipoExcecao
from tarvo.core.money import round_money
from tarvo.core.rastro import Rastro
from tarvo.engines.remessa import calcular_remessa
from tarvo.identity.registro import Registro
from tarvo.ingest.ponte import ler_ponte
from tarvo.ingest.taxas import ler_taxas
from tarvo.output.validators import validar_i_d1, validar_i_r1

MUNDO = "17217888000111"


@pytest.fixture(scope="module")
def corrida(dados):
    cfg = carregar_defaults()
    contratos, _ = ler_taxas(dados / "02_tabela_taxas_contratadas.xlsx")
    reg = Registro.construir(contratos, cfg.ecs_extra, cfg.sem_contrato, cfg.aliases)
    ops = ler_ponte(dados / "03_email_ponte_cambio_relatorio_set2026.eml")
    rastro = Rastro()
    res = calcular_remessa(ops, reg, Resolvedor(contratos, cfg.overrides), "2026-09", rastro)
    return res, rastro, ops


def test_total_commission_is_lucca_39543_45(corrida):
    res, _, _ = corrida
    assert sum(c["comissao_brl"] for c in res.comissoes) == D("39543.45")
    assert len(res.comissoes) == 14


def test_total_matches_independent_computation_from_raw_rows(corrida):
    _, _, ops = corrida
    unicas = {o.n_operacao: o for o in sorted(ops, key=lambda o: o.linha_fisica)}
    esperado = sum(round_money(D("0.5") * o.spread_brl) for o in unicas.values() if o.spread_brl > 0)
    assert esperado == D("39543.45")


def test_duplicate_is_counted_once_and_listed_for_ponte(corrida):
    res, rastro, _ = corrida
    dup = [e for e in res.excecoes if "duplicado" in e.motivo]
    assert [(e.ref_origem, e.valor_brl, e.quem_decide) for e in dup] == [("PC-0926-0162", D("410.94"), "Helena")]
    comissao_op = [l for l in rastro.linhas() if l.ref_origem == "PC-0926-0162" and l.id_saida.startswith("COM-REM")]
    assert len(comissao_op) == 1 and comissao_op[0].valor == D("410.94")


def test_four_negative_spreads_deviate_3565_98_from_contract(corrida):
    res, _, _ = corrida
    neg = [d for d in res.divergencias if D(d["taxa_aplicada_pct"]) < 0]
    assert sorted(d["ref_origem"] for d in neg) == ["PC-0926-0210", "PC-0926-0326", "PC-0926-0491", "PC-0926-0545"]
    assert sum(d["diferenca_brl"] for d in neg) == D("-3565.98")  # magnitude conferida; sinal = aplicado − contratado
    contest = [e for e in res.excecoes if "negativo" in e.motivo]
    assert len(contest) == 4 and all(e.tipo == TipoExcecao.CONTESTACAO_PONTE for e in contest)


def test_negative_operations_are_not_commissioned(corrida):
    _, rastro, _ = corrida
    com = {l.ref_origem for l in rastro.linhas() if l.id_saida.startswith("COM-REM")}
    assert not com & {"PC-0926-0210", "PC-0926-0326", "PC-0926-0491", "PC-0926-0545"}


def test_mundo_aberto_excess_is_1418_85_over_23_operations(corrida):
    res, _, _ = corrida
    mundo = [d for d in res.divergencias if d["cnpj"] == MUNDO]
    assert len(mundo) == 23 and sum(d["diferenca_brl"] for d in mundo) == D("1418.85")


def test_mundo_aberto_alternative_formula_is_three_cents_higher(corrida):
    """V8: Spread R$ − 1,2% × ME × PTAX dá R$ 1.418,88 (documentado em HIPOTESES R10)."""
    _, _, ops = corrida
    alt = sum(round_money(o.spread_brl - D("0.012") * o.valor_me * o.ptax) for o in ops if o.cnpj14 == MUNDO)
    assert alt == D("1418.88")


def test_only_mundo_aberto_and_the_negatives_diverge(corrida):
    """Ruído do Spread % (±0,0016 p.p.) fica abaixo da tolerância em todos os outros contratos."""
    res, _, _ = corrida
    assert len(res.divergencias) == 27
    assert collections.Counter(d["cnpj"] for d in res.divergencias if D(d["taxa_aplicada_pct"]) >= 0) == {MUNDO: 23}


def test_every_accepted_operation_is_in_the_rastro(corrida):
    _, rastro, ops = corrida
    assert {o.n_operacao for o in ops} <= {l.ref_origem for l in rastro.linhas()}


def test_invariants(corrida):
    res, rastro, _ = corrida
    pend = [{"id_saida": e.id_saida, "valor_brl": e.valor_brl} for e in res.excecoes]
    validar_i_r1({"comissoes_por_lojista": res.comissoes, "divergencias_taxa": res.divergencias,
                  "pendencias": pend}, rastro)
    validar_i_d1(res.divergencias)
    assert len(res.excecoes) == 28 and sum(e.valor_brl for e in res.excecoes) == D("-1736.19")
