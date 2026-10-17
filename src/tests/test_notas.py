import random
from decimal import Decimal as D

import pytest

from tarvo.core.excecoes import TipoExcecao
from tarvo.core.ids import id_comissao
from tarvo.core.rastro import Rastro
from tarvo.engines.notas import PONTE_CNPJ, PONTE_NOME, calcular_notas
from tarvo.output.validators import ValidationError, validar_i_n1, validar_i_r1

A, B, C = "11111111000111", "22222222000122", "33333333000133"


def _com(cnpj, valor, linha="CHECKOUT", nome=None):
    return {"id_saida": id_comissao(linha, cnpj, "2026-09"), "cnpj": cnpj, "lojista": nome or f"Loja {cnpj[:2]}",
            "linha_negocio": linha, "comissao_brl": D(valor)}


def _rastro(comissoes, partes=None):
    """Uma linha de rastro por comissão (ou as partes dadas), somando exatamente o reportado."""
    r = Rastro()
    for c in comissoes:
        ps = (partes or {}).get(c["id_saida"], [c["comissao_brl"]])
        assert sum(ps) == c["comissao_brl"]
        for i, v in enumerate(ps):
            arq = "01_orbe.csv" if c["linha_negocio"] == "CHECKOUT" else "03_ponte.eml"
            r.add(c["id_saida"], arq, f"{c['cnpj'][:2]}-{i}", v, regra_id="C1")
    return r


def _rodar(comissoes, partes=None, mes="2026-09"):
    r = _rastro(comissoes, partes)
    return calcular_notas(comissoes, r, mes), r


def test_checkout_note_per_merchant_with_fixed_template():
    res, _ = _rodar([_com(A, "100.00", nome="Loja A")])
    (n,) = res.notas
    assert n == {"id_saida": f"NF-CHK-{A}-202609", "tomador_cnpj": A, "tomador": "Loja A",
                 "linha_negocio": "CHECKOUT", "valor_brl": D("100.00"),
                 "discriminacao": "Comissão sobre serviços de checkout, competência 09/2026"}
    assert res.excecoes == []


@pytest.mark.parametrize("valor", ["0.00", "-5.50"])
def test_non_positive_checkout_commission_has_no_note_and_a_pending_for_helena(valor):
    res, r = _rodar([_com(A, valor)])
    assert res.notas == []
    (e,) = res.excecoes
    assert (e.tipo, e.quem_decide, e.valor_brl) == (TipoExcecao.COMISSAO_NAO_POSITIVA, "Helena", D(valor))
    assert e.ref_origem == f"{A}-202609"
    assert r.soma(e.id_saida) == D(valor)


def test_pending_rastro_uses_only_the_lines_that_make_the_amount():
    com = _com(A, "-5.50")
    res, r = _rodar([com], {com["id_saida"]: [D("0.00"), D("0.00"), D("-5.50"), D("0.00")]})
    linhas = [l for l in r.linhas() if l.id_saida == res.excecoes[0].id_saida]
    assert [l.valor for l in linhas] == [D("-5.50")]


def test_pending_rastro_falls_back_to_all_lines_when_everything_is_zero():
    com = _com(A, "0.00")
    res, r = _rodar([com], {com["id_saida"]: [D("0.00"), D("0.00")]})
    assert len([l for l in r.linhas() if l.id_saida == res.excecoes[0].id_saida]) == 2


def test_note_rastro_replicates_the_commission_lines():
    com = _com(A, "30.00")
    res, r = _rodar([com], {com["id_saida"]: [D("10.00"), D("20.00")]})
    nota = [(l.arquivo_origem, l.ref_origem, l.valor) for l in r.linhas() if l.id_saida == res.notas[0]["id_saida"]]
    base = [(l.arquivo_origem, l.ref_origem, l.valor) for l in r.linhas() if l.id_saida == com["id_saida"]]
    assert nota == base and sum(v for *_, v in nota) == D("30.00")


def test_remessa_is_a_single_note_to_ponte_with_the_total():
    coms = [_com(A, "100.00", "REMESSA"), _com(B, "50.50", "REMESSA")]
    res, r = _rodar(coms)
    (n,) = res.notas
    assert n["id_saida"] == "NF-REM-202609"
    assert (n["tomador_cnpj"], n["tomador"], n["linha_negocio"], n["valor_brl"]) == (
        PONTE_CNPJ, PONTE_NOME, "REMESSA", D("150.50"))
    assert PONTE_CNPJ == "75374179000146"
    assert n["discriminacao"] == "Comissão sobre serviços de intermediação de remessa internacional, competência 09/2026"
    assert r.soma("NF-REM-202609") == D("150.50")
    assert {l.ref_origem for l in r.linhas() if l.id_saida == "NF-REM-202609"} == {f"{A[:2]}-0", f"{B[:2]}-0"}


def test_merchant_with_both_lines_gets_checkout_note_and_its_remessa_goes_to_ponte():
    coms = [_com(A, "100.00", "CHECKOUT"), _com(A, "40.00", "REMESSA")]
    res, _ = _rodar(coms)
    por_id = {n["id_saida"]: n for n in res.notas}
    assert por_id[f"NF-CHK-{A}-202609"]["valor_brl"] == D("100.00")
    assert por_id["NF-REM-202609"]["valor_brl"] == D("40.00")


def test_no_remessa_commissions_means_no_remessa_note_and_no_pending():
    res, _ = _rodar([_com(A, "100.00")])
    assert [n["linha_negocio"] for n in res.notas] == ["CHECKOUT"] and res.excecoes == []


def test_non_positive_remessa_total_has_no_note_and_a_pending():
    res, r = _rodar([_com(A, "-10.00", "REMESSA"), _com(B, "4.00", "REMESSA")])
    assert res.notas == []
    (e,) = res.excecoes
    assert (e.tipo, e.ref_origem, e.valor_brl) == (TipoExcecao.COMISSAO_NAO_POSITIVA, "REMESSA-202609", D("-6.00"))
    assert r.soma(e.id_saida) == D("-6.00")


def test_mixed_batch_and_i_r1_holds():
    coms = [_com(A, "100.00"), _com(B, "-5.50"), _com(C, "0.00"), _com(A, "40.00", "REMESSA")]
    res, r = _rodar(coms)
    assert sorted(n["id_saida"] for n in res.notas) == sorted([f"NF-CHK-{A}-202609", "NF-REM-202609"])
    assert len(res.excecoes) == 2
    pend = [{"id_saida": e.id_saida, "valor_brl": e.valor_brl} for e in res.excecoes]
    validar_i_r1({"comissoes_por_lojista": coms, "notas_a_emitir": res.notas, "pendencias": pend}, r)
    validar_i_n1(res.notas)


def test_order_independent():
    coms = [_com(f"{i:02d}111111000111", f"{i}.37", "CHECKOUT" if i % 2 else "REMESSA") for i in range(1, 12)]
    a, _ = _rodar(coms)
    emb = coms[:]
    random.Random(1).shuffle(emb)
    b, _ = _rodar(emb)
    assert sorted(a.notas, key=lambda n: n["id_saida"]) == sorted(b.notas, key=lambda n: n["id_saida"])
    assert [e.id_saida for e in a.excecoes] == [e.id_saida for e in b.excecoes]


def test_i_n1_rejects_non_positive_note():
    with pytest.raises(ValidationError, match="NF-X"):
        validar_i_n1([{"id_saida": "NF-X", "valor_brl": D("0.00")}])
