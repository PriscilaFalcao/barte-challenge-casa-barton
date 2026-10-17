from decimal import Decimal

from tarvo.pipeline import fechar
from tarvo.web import _format_brl, _summary


def test_web_summary_matches_real_pipeline_outputs(dados, tmp_path):
    output = tmp_path / "saida"
    fechar("2026-09", dados, output)

    summary = _summary(output)

    assert summary["checkout"] == "R$ 207.039,73"
    assert summary["remessa"] == "R$ 39.543,45"
    assert summary["divergences_count"] == 233
    assert summary["notes_count"] == 21
    assert summary["pending_count"] == 18
    assert summary["pending_by_decider"] == {"Helena e Diego": 2, "Helena": 15, "Diego": 1}
    assert summary["reconciles"] is True


def test_brl_format_uses_brazilian_separators():
    assert _format_brl(Decimal("-1234567.89")) == "R$ -1.234.567,89"
