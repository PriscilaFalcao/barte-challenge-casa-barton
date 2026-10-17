from decimal import Decimal

import pytest

from tarvo.core.rastro import Rastro
from tarvo.output.writers import SCHEMAS, escrever_csv, escrever_rastro


def test_csv_format_semicolon_dot_decimal_and_header(tmp_path):
    p = tmp_path / "comissoes_por_lojista.csv"
    escrever_csv(p, "comissoes_por_lojista", [{
        "id_saida": "COM-CHK-66564512000199-202609", "cnpj": "66564512000199",
        "lojista": "Bridge; Viagens", "linha_negocio": "CHECKOUT", "comissao_brl": Decimal("-5.5"),
    }])
    linhas = p.read_text(encoding="utf-8").splitlines()
    assert linhas[0] == "id_saida;cnpj;lojista;linha_negocio;comissao_brl"
    assert linhas[1] == 'COM-CHK-66564512000199-202609;66564512000199;"Bridge; Viagens";CHECKOUT;-5.50'


def test_missing_required_column_fails(tmp_path):
    with pytest.raises(ValueError, match="comissao_brl"):
        escrever_csv(tmp_path / "x.csv", "comissoes_por_lojista", [
            {"id_saida": "A", "cnpj": "1", "lojista": "L", "linha_negocio": "CHECKOUT"}])


def test_invalid_enum_fails(tmp_path):
    with pytest.raises(ValueError, match="linha_negocio"):
        escrever_csv(tmp_path / "x.csv", "comissoes_por_lojista", [
            {"id_saida": "A", "cnpj": "1", "lojista": "L", "linha_negocio": "OUTRA", "comissao_brl": Decimal("1")}])


def test_cnpj_must_have_14_digits(tmp_path):
    with pytest.raises(ValueError, match="cnpj"):
        escrever_csv(tmp_path / "x.csv", "comissoes_por_lojista", [
            {"id_saida": "A", "cnpj": "123", "lojista": "L", "linha_negocio": "CHECKOUT", "comissao_brl": Decimal("1")}])


def test_confianca_range(tmp_path):
    base = {"id_saida": "A", "banco": "AURORA", "ref_origem": "L9", "data": "2026-09-01",
            "descricao": "d", "valor": Decimal("1"), "conta_codigo": "1.1.01.001", "metodo": "REGRA"}
    with pytest.raises(ValueError, match="confianca"):
        escrever_csv(tmp_path / "x.csv", "lancamentos_classificados", [{**base, "confianca": Decimal("1.5")}])


def test_output_is_independent_of_input_order(tmp_path):
    a = {"id_saida": "COM-A", "cnpj": "11111111000111", "lojista": "A", "linha_negocio": "CHECKOUT", "comissao_brl": Decimal("1")}
    b = {**a, "id_saida": "COM-B"}
    escrever_csv(tmp_path / "1.csv", "comissoes_por_lojista", [a, b])
    escrever_csv(tmp_path / "2.csv", "comissoes_por_lojista", [b, a])
    assert (tmp_path / "1.csv").read_bytes() == (tmp_path / "2.csv").read_bytes()


def test_rastro_csv_has_required_and_extra_columns(tmp_path):
    r = Rastro()
    r.add("COM-A", "01_orbe.csv", "TX1", Decimal("1.2"), componente="MDR", taxa_usada_pct="1.49", regra_id="C1")
    p = tmp_path / "rastro.csv"
    escrever_rastro(p, r)
    linhas = p.read_text(encoding="utf-8").splitlines()
    assert linhas[0].startswith("id_saida;arquivo_origem;ref_origem;valor")
    assert linhas[1] == "COM-A;01_orbe.csv;TX1;1.20;MDR;1.49;C1"


def test_schemas_cover_the_six_outputs():
    assert set(SCHEMAS) == {
        "comissoes_por_lojista", "divergencias_taxa", "notas_a_emitir",
        "lancamentos_classificados", "pendencias", "rastro",
    }
