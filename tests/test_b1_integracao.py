"""B1 de ponta a ponta com o data pack real: Orbe + Taxas + registro + resolvedor.

Números conferidos contra HIPOTESES.md: só Casa (tarifa zero), Bridge (vendas pós-15/09 ao preço antigo)
e Rota (+0,50 p.p. em crédito) têm taxa aplicada diferente da contratada. Débito e Pix da Rota não.
"""
import collections
from decimal import Decimal

import pytest

from tarvo.config import carregar_defaults
from tarvo.contracts.resolver import Resolvedor, produto_de
from tarvo.identity.registro import Registro
from tarvo.ingest.orbe import ler_orbe
from tarvo.ingest.taxas import ler_taxas


@pytest.fixture(scope="module")
def ambiente(dados):
    cfg = carregar_defaults()
    contratos, excecoes = ler_taxas(dados / "02_tabela_taxas_contratadas.xlsx")
    reg = Registro.construir(contratos, cfg.ecs_extra, cfg.sem_contrato, cfg.aliases)
    return reg, Resolvedor(contratos, cfg.overrides), ler_orbe(dados / "01_orbe_relatorio_comissoes_set2026.csv"), excecoes


def _contratada(reg, rs, t):
    loj = reg.classificar(ec=t.cod_estabelecimento).lojista
    if t.tipo in ("ANTECIPACAO", "REVERSAO_ANTECIPACAO"):
        prod = "ANTECIPACAO"
        dia = t.data_movimento if t.tipo == "ANTECIPACAO" else t.data_venda_original
    else:
        prod = produto_de(t.modalidade, t.qtd_parcelas)
        dia = t.data_movimento if t.tipo == "VENDA" else t.data_venda_original
    return loj, prod, rs.taxa(loj.cnpj14, prod, dia).pct


def test_every_non_atlas_line_resolves_a_rate_without_exception(ambiente):
    reg, rs, txs, excecoes = ambiente
    assert excecoes == []
    resolvidas = [_contratada(reg, rs, t) for t in txs if reg.classificar(ec=t.cod_estabelecimento).lojista]
    assert len(resolvidas) == 1886


def test_only_casa_bridge_and_rota_differ_from_contract(ambiente):
    reg, rs, txs, _ = ambiente
    difere = collections.Counter()
    for t in txs:
        if not reg.classificar(ec=t.cod_estabelecimento).lojista:
            continue
        loj, prod, pct = _contratada(reg, rs, t)
        if pct != t.taxa_aplicada_pct:
            difere[(loj.nome_canonico, t.tipo if t.tipo != "VENDA" else prod)] += 1
    por_lojista = collections.Counter()
    for (nome, _), n in difere.items():
        por_lojista[nome] += n
    assert por_lojista == {
        "Casa do Estudante Viagens Ltda": 118,
        "Escola Bridge de Idiomas Ltda": 5,
        "Rota Global Intercâmbio Ltda": 87,
    }


def test_rota_debit_and_pix_have_no_divergence(ambiente):
    reg, rs, txs, _ = ambiente
    for t in txs:
        loj = reg.classificar(ec=t.cod_estabelecimento).lojista
        if loj and loj.nome_canonico.startswith("Rota") and t.modalidade in ("DEBITO", "PIX"):
            assert _contratada(reg, rs, t)[2] == t.taxa_aplicada_pct


def test_rota_credit_diverges_by_exactly_half_point(ambiente):
    reg, rs, txs, _ = ambiente
    difs = {t.taxa_aplicada_pct - _contratada(reg, rs, t)[2] for t in txs
            if (loj := reg.classificar(ec=t.cod_estabelecimento).lojista)
            and loj.nome_canonico.startswith("Rota") and t.modalidade.startswith("CREDITO")
            and t.taxa_aplicada_pct != _contratada(reg, rs, t)[2]}
    assert difs == {Decimal("0.50")}


def test_casa_contracted_rate_is_zero_everywhere(ambiente):
    reg, rs, txs, _ = ambiente
    taxas = {_contratada(reg, rs, t)[2] for t in txs
             if (loj := reg.classificar(ec=t.cod_estabelecimento).lojista)
             and loj.nome_canonico.startswith("Casa") and t.data_movimento.month == 9
             and (t.data_venda_original or t.data_movimento).month == 9}
    assert taxas == {Decimal("0")}
