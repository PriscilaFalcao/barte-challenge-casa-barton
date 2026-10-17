"""B7: pendências com quem_decide e bloqueante vindos da configuração, I-R2 e resumo.md."""
import csv
from decimal import Decimal as D

import pytest

from tarvo.cli import main
from tarvo.config import carregar_defaults
from tarvo.core.excecoes import TipoExcecao
from tarvo.core.rastro import Rastro
from tarvo.ingest.plano_contas import Conta
from tarvo.output.resumo import brl, gerar_resumo
from tarvo.output.validators import ValidationError, validar_i_r2


def _ler(p):
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


@pytest.fixture(scope="module")
def saida(dados, tmp_path_factory):
    out = tmp_path_factory.mktemp("saida")
    main(["fechar", "--mes", "2026-09", "--dados", str(dados), "--saida", str(out)])
    return out


# --- configuração ---------------------------------------------------------------------------------------

def test_every_exception_type_has_an_owner_in_config():
    cfg = carregar_defaults()
    assert set(cfg.quem_decide) == set(TipoExcecao)
    assert cfg.quem_decide[TipoExcecao.CONTRATO_AMBIGUO] == "Comercial"  # ✅ cadastro e contrato: comercial


def test_owner_and_blocking_come_from_config(tmp_path):
    p = tmp_path / "d.yaml"
    p.write_text("quem_decide:\n  DIVERGENCIA_ORBE: Bia\nbloqueantes: [DIVERGENCIA_ORBE]\n", encoding="utf-8")
    cfg = carregar_defaults(p)
    assert cfg.quem_decide == {TipoExcecao.DIVERGENCIA_ORBE: "Bia"}
    assert cfg.bloqueantes == {TipoExcecao.DIVERGENCIA_ORBE}


def test_unknown_type_in_config_fails(tmp_path):
    p = tmp_path / "d.yaml"
    p.write_text("bloqueantes: [NAO_EXISTE]\n", encoding="utf-8")
    with pytest.raises(ValueError):
        carregar_defaults(p)


# --- I-R2 -----------------------------------------------------------------------------------------------

def test_i_r2_accepts_refs_that_exist():
    r = Rastro()
    r.add("COM-1", "orbe.csv", "TX1", D("1.00"))
    validar_i_r2({"orbe.csv": {"TX1", "TX2"}}, r)


def test_i_r2_rejects_ref_or_file_that_does_not_exist():
    r = Rastro()
    r.add("COM-1", "orbe.csv", "TX9", D("1.00"))
    r.add("COM-2", "outro.csv", "L1", D("1.00"))
    with pytest.raises(ValidationError) as e:
        validar_i_r2({"orbe.csv": {"TX1"}}, r)
    assert "TX9" in str(e.value) and "outro.csv" in str(e.value)


# --- resumo.md ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("v,txt", [("1546.28", "R$ 1.546,28"), ("-300000", "−R$ 300.000,00"), ("0.5", "R$ 0,50"),
                                   ("7", "R$ 7,00")])
def test_brl_is_brazilian_format(v, txt):
    assert brl(D(v)) == txt


def _pend(tipo, ref, valor, quem="Financeiro", bloq="N"):
    return {"id_saida": f"PEN-{tipo}-{ref}", "tipo": tipo, "ref_origem": ref, "valor_brl": D(valor),
            "motivo": "m | com barra", "quem_decide": quem, "bloqueante": bloq}


def _resumo(pendencias):
    com = [{"cnpj": "11111111000111", "lojista": "Loja Um", "linha_negocio": "CHECKOUT", "comissao_brl": D("10.00")}]
    lan = [{"banco": "AURORA", "conta_codigo": "4.2.01", "valor": D("-1.00"), "metodo": "REGRA"}]
    return gerar_resumo("2026-09", com, [], [], lan, pendencias, {"4.2.01": Conta("4.2.01", "Tarifas", True)}, "ok")


def test_resumo_says_ready_only_without_blocking_pendings():
    assert "Pronto para fechar" in _resumo([_pend("DIVERGENCIA_ORBE", "X", "1")])
    txt = _resumo([_pend("CONTRATO_AMBIGUO", "Taxas!L6", "0", "Comercial", "S")])
    assert "Não fechar ainda" in txt and "**bloqueante**" in txt


def test_resumo_does_not_add_up_pendings_of_different_nature():
    txt = _resumo([_pend("CONFERIR_MES_SEGUINTE", "L92", "-300000"), _pend("CONFERIR_MES_SEGUINTE", "M1", "18240")])
    assert "−R$ 300.000,00" in txt and "R$ 18.240,00" in txt
    assert "281.760" not in txt  # a soma das duas não aparece em lugar nenhum


def test_resumo_shows_merchant_name_for_grouped_pendings_and_escapes_pipes():
    txt = _resumo([_pend("DIVERGENCIA_ORBE", "11111111000111-202609", "5")])
    assert "Loja Um (11111111000111-202609)" in txt and "m / com barra" in txt


def test_real_resumo_has_the_key_numbers(saida):
    txt = (saida / "resumo.md").read_text(encoding="utf-8")
    for esperado in ("R$ 203.735,34", "R$ 39.543,45", "R$ 243.284,29", "R$ 15.397,42", "Pronto para fechar",
                     "I-R1, I-R2, I-R3, I-D1, I-N1, I-C1 ok", "### Financeiro e Comercial (2)", "### Comercial (1)"):
        assert esperado in txt, esperado


def test_pendencias_csv_has_blocking_column_and_owners_from_config(saida):
    pend = _ler(saida / "pendencias.csv")
    assert {p["bloqueante"] for p in pend} == {"N"}
    por_tipo = {p["tipo"]: p["quem_decide"] for p in pend}
    assert por_tipo["SEM_CONTRATO"] == "Comercial" and por_tipo["DEVOLUCAO_LOJISTA"] == "Financeiro e Comercial"


def test_resumo_is_identical_between_runs(saida, dados, tmp_path):
    main(["fechar", "--mes", "2026-09", "--dados", str(dados), "--saida", str(tmp_path)])
    assert (tmp_path / "resumo.md").read_bytes() == (saida / "resumo.md").read_bytes()
