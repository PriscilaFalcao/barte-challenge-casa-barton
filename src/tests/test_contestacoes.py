"""Rascunhos de contestação (✅ Helena, Casa Barton 11h01): um texto por contraparte, com o detalhe anexado."""
from tarvo.output.contestacoes import gerar_rascunhos
from tarvo.pipeline import fechar


def test_drafts_carry_the_same_totals_as_the_pendings(dados, tmp_path):
    fechar("2026-09", dados, tmp_path)
    texto = (tmp_path / "rascunhos_contestacao.md").read_text(encoding="utf-8")
    assert "Rascunho, não enviado" in texto
    # Ponte: excesso da Mundo Aberto, 4 spreads negativos até o contrato e a duplicata
    for esperado in ("R$ 1.418,85", "R$ 3.565,98", "R$ 410,94", "PC-0926-0162", "PC-0926-0210", "−R$ 687,52",
                     "R$ 1.351,87"):
        assert esperado in texto
    # Orbe: só a diferença líquida de Rota e Bridge; a Casa fica fora, como decisão interna
    assert "R$ 1.576,23" in texto and "TX88428053" in texto
    assert texto.index("## Fora das contestações") > texto.index("## Orbe")
    fora = texto[texto.index("## Fora das contestações"):]
    assert "Casa do Estudante" in fora and "R$ 15.396,77" in fora and "TX88410932" not in texto
    assert "2.438,46" in texto and "4,0315" in texto  # números em formato brasileiro


def test_no_counterpart_issue_says_so():
    texto = gerar_rascunhos("2026-10", [], [], [], [], [], {})
    assert "Nenhuma contestação neste mês." in texto and "## Ponte" not in texto
