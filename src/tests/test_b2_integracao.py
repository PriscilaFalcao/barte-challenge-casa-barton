"""B2 com o data pack real. Os números ✅ vêm de HIPOTESES.md; os "regressão" foram fixados após
inspeção das linhas de rastro (PRD seção 10: "≈" só vira exato depois de conferido)."""
import collections
from decimal import Decimal as D

import pytest

from tarvo.config import carregar_defaults
from tarvo.contracts.resolver import Resolvedor
from tarvo.core.excecoes import TipoExcecao
from tarvo.core.rastro import Rastro
from tarvo.engines.checkout import calcular_checkout
from tarvo.identity.registro import Registro
from tarvo.ingest.orbe import ler_orbe
from tarvo.ingest.taxas import ler_taxas
from tarvo.output.validators import validar_i_r1


@pytest.fixture(scope="module")
def corrida(dados):
    cfg = carregar_defaults()
    contratos, _ = ler_taxas(dados / "02_tabela_taxas_contratadas.xlsx")
    reg = Registro.construir(contratos, cfg.ecs_extra, cfg.sem_contrato, cfg.aliases)
    txs = ler_orbe(dados / "01_orbe_relatorio_comissoes_set2026.csv")
    rastro = Rastro()
    res = calcular_checkout(txs, reg, Resolvedor(contratos, cfg.overrides), "2026-09", rastro)
    return res, rastro, txs


def test_i_r1_holds_for_comissoes_and_pendencias(corrida):
    res, rastro, _ = corrida
    pend = [{"id_saida": e.id_saida, "valor_brl": e.valor_brl} for e in res.excecoes]
    validar_i_r1({"comissoes_por_lojista": res.comissoes, "pendencias": pend}, rastro)


def test_every_orbe_line_of_the_month_is_in_the_rastro_exactly_once(corrida):
    _, rastro, txs = corrida
    cont = collections.Counter(l.ref_origem for l in rastro.linhas())
    assert set(cont) == {t.id_transacao for t in txs} and set(cont.values()) == {1}


def test_casa_commission_is_minus_5_50_the_august_estorno(corrida):
    res, _, _ = corrida
    casa = next(c for c in res.comissoes if c["lojista"].startswith("Casa"))
    assert casa["comissao_brl"] == D("-5.50")  # PRD 7.6: estorno TX88445133 de venda de 21/08 a 1,49%


def test_atlas_is_out_of_commissions_and_is_a_pending_for_diego(corrida):
    res, rastro, _ = corrida
    assert all(c["cnpj"] != "39566044000119" and "Atlas" not in c["lojista"] for c in res.comissoes)
    (e,) = res.excecoes
    assert (e.tipo, e.ref_origem, e.quem_decide) == (TipoExcecao.SEM_CONTRATO, "1076801732", "Diego")
    assert len([l for l in rastro.linhas() if l.id_saida == e.id_saida]) == 57
    assert e.valor_brl == D("7876.05")


def test_orbe_fee_totals_match_fox_figures_so_the_pack_reading_is_right(corrida):
    _, _, txs = corrida
    s = collections.defaultdict(D)
    for t in txs:
        s[t.tipo] += t.valor_taxa
    assert dict(s) == {"VENDA": D("214558.33"), "ESTORNO": D("-7108.69"),
                       "ANTECIPACAO": D("30491.41"), "REVERSAO_ANTECIPACAO": D("-6060.69")}


def test_line_commission_equals_orbe_fee_minus_overcharge_within_truncation(corrida):
    """Identidade independente: taxa Orbe − comissão = bruto × (aplicada − contratada), com folga de 1,5 centavo
    (truncagem da Orbe, até 0,01, mais o arredondamento da comissão, até 0,005)."""
    res, _, _ = corrida
    for l in res.linhas:
        excesso = l.tx.valor_bruto * (l.tx.taxa_aplicada_pct - l.taxa.pct) / 100
        assert abs((l.tx.valor_taxa - l.comissao) - excesso) <= D("0.015"), l.tx.id_transacao


def test_reversal_cancels_the_commission_of_the_reversed_antecipation(corrida):
    res, _, _ = corrida
    por_id = {l.tx.id_transacao: l for l in res.linhas}
    reversoes = [l for l in res.linhas if l.tx.tipo == "REVERSAO_ANTECIPACAO"]
    assert len(reversoes) == 4  # das 6 reversões do mês, 2 são da Atlas (fora)
    for r in reversoes:
        assert r.comissao == -por_id[r.tx.id_referencia].comissao


def test_rule_tags(corrida):
    res, _, _ = corrida
    assert collections.Counter(l.regra_id for l in res.linhas) == {
        "C1": 1678, "C8": 118, "C3": 48, "C4": 33, "C3-HISTORICO": 9}


def test_regression_totals(corrida):
    res, _, _ = corrida
    assert len(res.comissoes) == 21
    assert sum(c["comissao_brl"] for c in res.comissoes) == D("207039.73")
