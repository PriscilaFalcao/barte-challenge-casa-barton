from datetime import date

from tarvo.core.competencia import no_mes
from tarvo.core.ledger import Ledger


def test_no_mes():
    assert no_mes(date(2026, 9, 30), "2026-09") and not no_mes(date(2026, 10, 1), "2026-09")
    assert not no_mes(date(2026, 8, 31), "2026-09")


def test_counts_by_source_and_reason():
    l = Ledger()
    l.ignorar("Orbe", "fora do mês", "TX1")
    l.ignorar("Orbe", "fora do mês", "TX2")
    l.ignorar("Ponte", "rodapé ou linha sem dado", "L240")
    assert l.contar("Orbe", "fora do mês") == 2
    assert l.contar("Ponte", "rodapé ou linha sem dado") == 1
    assert l.contar("Ponte", "fora do mês") == 0


def test_sample_is_capped_and_deterministic():
    a, b = Ledger(), Ledger()
    refs = [f"TX{i:02d}" for i in range(20)]
    for r in refs:
        a.ignorar("Orbe", "fora do mês", r)
    for r in reversed(refs):
        b.ignorar("Orbe", "fora do mês", r)
    assert a.linhas_log() == b.linhas_log()
    assert a.linhas_log() == ["Orbe: 20 linha(s) ignorada(s) (fora do mês); ex.: TX00, TX01, TX02, TX03, TX04"]


def test_empty_ledger_has_no_log_lines():
    assert Ledger().linhas_log() == []
