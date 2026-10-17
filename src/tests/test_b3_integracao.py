"""B3 com o data pack real. Números conferidos em HIPOTESES.md e no PRD seção 10."""
import collections
from decimal import Decimal as D

import pytest

from tarvo.config import carregar_defaults
from tarvo.contracts.resolver import Resolvedor
from tarvo.core.rastro import Rastro
from tarvo.engines.checkout import calcular_checkout
from tarvo.engines.divergencias import calcular_divergencias
from tarvo.identity.registro import Registro
from tarvo.ingest.orbe import ler_orbe
from tarvo.ingest.taxas import ler_taxas
from tarvo.output.validators import validar_i_d1, validar_i_r1

CASA, ROTA, BRIDGE = "00520815000100", "95927868000148", "22224579000109"


@pytest.fixture(scope="module")
def corrida(dados):
    cfg = carregar_defaults()
    contratos, _ = ler_taxas(dados / "02_tabela_taxas_contratadas.xlsx")
    reg = Registro.construir(contratos, cfg.ecs_extra, cfg.sem_contrato, cfg.aliases)
    txs = ler_orbe(dados / "01_orbe_relatorio_comissoes_set2026.csv")
    rastro = Rastro()
    chk = calcular_checkout(txs, reg, Resolvedor(contratos, cfg.overrides), "2026-09", rastro)
    div = calcular_divergencias(chk.linhas, rastro)
    return chk, div, rastro


def _por_cnpj(div):
    n, v = collections.Counter(), collections.defaultdict(D)
    for d in div.divergencias:
        n[d["cnpj"]] += 1
        v[d["cnpj"]] += d["diferenca_brl"]
    return n, v


def test_only_casa_rota_and_bridge_diverge(corrida):
    _, div, _ = corrida
    n, v = _por_cnpj(div)
    assert dict(n) == {CASA: 118, ROTA: 87, BRIDGE: 5}
    assert (v[CASA], v[ROTA], v[BRIDGE]) == (D("15397.42"), D("1546.28"), D("29.95"))


def test_casa_charged_about_15_4k(corrida):
    _, div, _ = corrida
    cobrado = sum(d["diferenca_brl"] for d in div.divergencias if d["cnpj"] == CASA and d["diferenca_brl"] > 0)
    assert D("15400") < cobrado < D("15410")  # PRD: "≈ R$ 15,4 mil"; estornos de set abatem no líquido


def test_rota_debit_and_pix_have_no_divergence_and_credit_is_half_point(corrida):
    chk, div, _ = corrida
    divergentes = {d["ref_origem"] for d in div.divergencias}
    rota = [l for l in chk.linhas if l.cnpj14 == ROTA]
    assert all(l.tx.id_transacao not in divergentes for l in rota if l.produto in ("DEBITO", "PIX"))
    credito = [l for l in rota if l.produto.startswith("CREDITO") and l.tx.id_transacao in divergentes]
    assert credito and {l.tx.taxa_aplicada_pct - l.taxa.pct for l in credito} == {D("0.50")}


def test_estornos_of_rota_credit_are_negative_divergences(corrida):
    _, div, _ = corrida
    neg = [d for d in div.divergencias if d["cnpj"] == ROTA and d["diferenca_brl"] < 0]
    assert len(neg) == 4  # 1 + 2 + 1 estornos de crédito vendidos após 12/09


def test_truncation_noise_creates_no_divergence(corrida):
    """855 linhas com taxa igual à contratada têm centavo de diferença (truncagem da Orbe); nenhuma é alarme."""
    chk, div, _ = corrida
    divergentes = {d["ref_origem"] for d in div.divergencias}
    ruido = [l for l in chk.linhas if l.tx.taxa_aplicada_pct == l.taxa.pct and l.comissao != l.tx.valor_taxa]
    assert len(ruido) == 855
    assert all(l.tx.id_transacao not in divergentes for l in ruido)


def test_divergence_amount_matches_independent_identity(corrida):
    chk, div, _ = corrida
    por_ref = {l.tx.id_transacao: l for l in chk.linhas}
    for d in div.divergencias:
        l = por_ref[d["ref_origem"]]
        assert abs((l.tx.valor_taxa - l.comissao) - d["diferenca_brl"]) <= D("0.015"), d["ref_origem"]


def test_invariants_and_pending_per_divergence(corrida):
    chk, div, rastro = corrida
    validar_i_d1(div.divergencias)
    pend = [{"id_saida": e.id_saida, "valor_brl": e.valor_brl} for e in chk.excecoes + div.excecoes]
    validar_i_r1({"comissoes_por_lojista": chk.comissoes, "divergencias_taxa": div.divergencias,
                  "pendencias": pend}, rastro)
    assert len(div.excecoes) == 210 and {e.quem_decide for e in div.excecoes} == {"Helena"}
