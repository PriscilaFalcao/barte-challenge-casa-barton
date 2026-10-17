"""B8: estado em SQLite, eventos por etapa, checkpoint, fila, decisões humanas e regras promovidas."""
import csv
import shutil
from decimal import Decimal as D

import pytest

from tarvo.cli import main
from tarvo.estado.checkpoint import Checkpoints, fingerprint
from tarvo.estado.db import AGUARDANDO, DECIDIDA, RESOLVIDA, Estado
from tarvo.pipeline import fechar

AURORA = "05a_extrato_banco_aurora_cc4471_set2026.csv"
CALCULO = ["ingestao", "checkout", "divergencias", "remessa", "notas", "bancos"]


def _ler(p):
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


@pytest.fixture
def dados_sem_regra(dados, tmp_path):
    """Data pack com uma descrição que nenhuma regra conhece (como um fornecedor novo em outubro)."""
    d = tmp_path / "dados"
    shutil.copytree(dados, d)
    p = d / AURORA
    txt = p.read_text(encoding="utf-8")
    assert "PIX ENVIADO CONTABILIDADE EXATA LTDA" in txt
    p.write_text(txt.replace("PIX ENVIADO CONTABILIDADE EXATA LTDA", "BOLETO GRAFICA RAPIDA LTDA"), encoding="utf-8")
    return d


def _status(res):
    return dict(res.etapas)


def test_second_run_reuses_every_calculation_stage_and_outputs_are_identical(dados, tmp_path):
    est = tmp_path / "est"
    r1 = fechar("2026-09", dados, tmp_path / "s1", est, cliente=None)
    r2 = fechar("2026-09", dados, tmp_path / "s2", est, cliente=None)
    assert {e: _status(r1)[e] for e in CALCULO} == {e: "executada" for e in CALCULO}
    assert {e: _status(r2)[e] for e in CALCULO} == {e: "reaproveitada" for e in CALCULO}
    for arq in (tmp_path / "s1").iterdir():
        assert arq.read_bytes() == (tmp_path / "s2" / arq.name).read_bytes(), arq.name


def test_run_with_state_equals_run_without_state(dados, tmp_path):
    fechar("2026-09", dados, tmp_path / "com", tmp_path / "est", cliente=None)
    fechar("2026-09", dados, tmp_path / "sem", None, cliente=None)
    for arq in (tmp_path / "com").iterdir():
        assert arq.read_bytes() == (tmp_path / "sem" / arq.name).read_bytes(), arq.name


def test_events_are_recorded_per_stage(dados, tmp_path):
    res = fechar("2026-09", dados, tmp_path / "s", tmp_path / "est", cliente=None)
    db = Estado(tmp_path / "est")
    ev = db.eventos(res.execucao_id)
    assert [e["etapa"] for e in ev] == CALCULO + ["agentes", "consolidacao"]
    assert ev[0]["detalhe"]["orbe"] == 1943 and ev[-1]["detalhe"]["pendencias"] == 18
    assert db.ultima_execucao("2026-09")["status"] == "CONCLUIDA"


def test_failed_run_is_recorded_as_error(dados, tmp_path):
    with pytest.raises(Exception, match="outro mês"):
        fechar("2026-10", dados, tmp_path / "s", tmp_path / "est", cliente=None)
    assert Estado(tmp_path / "est").ultima_execucao("2026-10")["status"] == "ERRO"


def test_queue_mirrors_pendings(dados, tmp_path):
    fechar("2026-09", dados, tmp_path / "s", tmp_path / "est", cliente=None)
    fila = Estado(tmp_path / "est").fila("2026-09")
    assert len(fila) == 18 and {i["estado"] for i in fila} == {AGUARDANDO}


def test_line_without_rule_goes_to_provisional_account_and_queue(dados_sem_regra, tmp_path):
    fechar("2026-09", dados_sem_regra, tmp_path / "s", tmp_path / "est", cliente=None)
    l53 = next(l for l in _ler(tmp_path / "s" / "lancamentos_classificados.csv") if l["ref_origem"] == "L53")
    assert (l53["conta_codigo"], l53["metodo"], l53["confianca"]) == ("1.1.03.003", "HUMANO", "0.00")
    assert Estado(tmp_path / "est").item_fila("2026-09", "PEN-CLASSIFICACAO_BAIXA_CONFIANCA-L53")["estado"] == AGUARDANDO


def test_human_account_decision_recomputes_only_banks(dados_sem_regra, tmp_path):
    est, s = tmp_path / "est", tmp_path / "s"
    fechar("2026-09", dados_sem_regra, s, est, cliente=None)
    main(["decidir", "--mes", "2026-09", "--id", "PEN-CLASSIFICACAO_BAIXA_CONFIANCA-L53", "--por", "Helena",
          "--motivo", "gráfica é serviço de terceiros", "--conta", "4.2.06", "--dados", str(dados_sem_regra),
          "--estado", str(est)])
    res = fechar("2026-09", dados_sem_regra, s, est, cliente=None)
    st = _status(res)
    assert st["bancos"] == "executada"
    assert all(st[e] == "reaproveitada" for e in ("ingestao", "checkout", "divergencias", "remessa", "notas"))
    l53 = next(l for l in _ler(s / "lancamentos_classificados.csv") if l["ref_origem"] == "L53")
    assert (l53["conta_codigo"], l53["metodo"], l53["confianca"]) == ("4.2.06", "HUMANO", "1.00")
    assert all(p["ref_origem"] != "L53" for p in _ler(s / "pendencias.csv"))
    assert Estado(est).item_fila("2026-09", "PEN-CLASSIFICACAO_BAIXA_CONFIANCA-L53")["estado"] == RESOLVIDA


def test_promoted_rule_applies_and_can_be_reverted(dados_sem_regra, tmp_path):
    est, s = tmp_path / "est", tmp_path / "s"
    fechar("2026-09", dados_sem_regra, s, est, cliente=None)
    main(["decidir", "--mes", "2026-09", "--id", "PEN-CLASSIFICACAO_BAIXA_CONFIANCA-L53", "--por", "Helena",
          "--motivo", "toda gráfica é serviço", "--conta", "4.2.06", "--escopo", "regra", "--banco", "AURORA",
          "--padrao", "^boleto grafica", "--dados", str(dados_sem_regra), "--estado", str(est)])
    db = Estado(est)
    (regra,) = db.regras()
    assert regra["tipo"] == "PADRAO_CONTA" and regra["autor"] == "Helena"
    # Simula o mês seguinte: a decisão do caso (L53 deste mês) não vale mais; a regra promovida, sim.
    db.con.execute("UPDATE decisoes SET ativa = 0")
    db.con.commit()
    fechar("2026-09", dados_sem_regra, s, est, cliente=None)
    l53 = next(l for l in _ler(s / "lancamentos_classificados.csv") if l["ref_origem"] == "L53")
    assert (l53["conta_codigo"], l53["metodo"], l53["regra_id"]) == ("4.2.06", "REGRA", f"HUM-{regra['decisao_id']}")
    db.desativar_regra(regra["id"])  # reverter volta ao resultado anterior
    fechar("2026-09", dados_sem_regra, s, est, cliente=None)
    l53 = next(l for l in _ler(s / "lancamentos_classificados.csv") if l["ref_origem"] == "L53")
    assert l53["metodo"] == "HUMANO" and l53["conta_codigo"] == "1.1.03.003"


def test_registry_change_recomputes_checkout_side_but_not_banks(dados, tmp_path):
    est = tmp_path / "est"
    fechar("2026-09", dados, tmp_path / "s", est, cliente=None)
    db = Estado(est)
    db.promover_regra("EC_LOJISTA", {"ec": "9999999999", "cnpj": "66564512000199"}, "Diego", "EC novo", None)
    db.fechar()
    st = _status(fechar("2026-09", dados, tmp_path / "s", est, cliente=None))
    assert [st[e] for e in CALCULO] == ["reaproveitada", "executada", "executada", "executada", "executada",
                                        "reaproveitada"]


def test_note_decision_is_recorded_in_pendencias_without_changing_numbers(dados, tmp_path):
    est, s = tmp_path / "est", tmp_path / "s"
    fechar("2026-09", dados, s, est, cliente=None)
    antes = (s / "comissoes_por_lojista.csv").read_bytes()
    main(["decidir", "--mes", "2026-09", "--id", "PEN-DIVERGENCIA_ORBE-22224579000109-202609", "--por", "Helena",
          "--motivo", "cobrar a Orbe", "--nota", "cobrar R$ 29,95 da Orbe e devolver à Bridge", "--estado", str(est)])
    res = fechar("2026-09", dados, s, est, cliente=None)
    assert all(v == "reaproveitada" for e, v in res.etapas if e in CALCULO)
    p = next(p for p in _ler(s / "pendencias.csv") if p["id_saida"] == "PEN-DIVERGENCIA_ORBE-22224579000109-202609")
    assert p["decisao"] == "Helena: cobrar R$ 29,95 da Orbe e devolver à Bridge"
    assert (s / "comissoes_por_lojista.csv").read_bytes() == antes
    assert Estado(est).item_fila("2026-09", p["id_saida"])["estado"] == DECIDIDA


def test_decision_requires_author_reason_and_known_item(dados, tmp_path):
    est = tmp_path / "est"
    fechar("2026-09", dados, tmp_path / "s", est, cliente=None)
    with pytest.raises(SystemExit, match="não está na fila"):
        main(["decidir", "--mes", "2026-09", "--id", "PEN-X", "--por", "H", "--motivo", "m", "--nota", "x",
              "--estado", str(est)])
    with pytest.raises(ValueError, match="autor e motivo"):
        Estado(est).registrar_decisao("2026-09", "PEN-X", "NOTA", {}, "caso", "", "")


def test_decision_with_synthetic_account_is_refused(dados_sem_regra, tmp_path):
    est = tmp_path / "est"
    fechar("2026-09", dados_sem_regra, tmp_path / "s", est, cliente=None)
    with pytest.raises(SystemExit, match="não aceita lançamento"):
        main(["decidir", "--mes", "2026-09", "--id", "PEN-CLASSIFICACAO_BAIXA_CONFIANCA-L53", "--por", "H",
              "--motivo", "m", "--conta", "4.2", "--dados", str(dados_sem_regra), "--estado", str(est)])


def test_checkpoint_with_other_fingerprint_is_ignored(tmp_path):
    ck = Checkpoints(tmp_path, "2026-09")
    ck.salvar("x", fingerprint("x", 1), {"v": 1})
    assert ck.carregar("x", fingerprint("x", 1)) == {"v": 1}
    assert ck.carregar("x", fingerprint("x", 2)) is None
    (tmp_path / "execucoes" / "2026-09" / "x.pkl").write_bytes(b"lixo")
    assert ck.carregar("x", fingerprint("x", 1)) is None  # corrompido: recalcula


def test_cli_fechar_prints_stages(dados, tmp_path, capsys):
    main(["fechar", "--mes", "2026-09", "--dados", str(dados), "--saida", str(tmp_path / "s"),
          "--estado", str(tmp_path / "est")])
    assert "etapas: ingestao (executada)" in capsys.readouterr().out
