"""B8/B11: orquestrador, Classificador, InterpreteTaxas e Investigador com cliente falso (sem API)."""
import csv
import json
import shutil
from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace

import pytest

from tarvo.agents import classificador, interprete_taxas, investigador
from tarvo.agents.base import Agente, ClienteAnthropic, cliente_padrao
from tarvo.pipeline import fechar

AURORA = "05a_extrato_banco_aurora_cc4471_set2026.csv"


class Falso:
    """Responde por agente (pelo modelo/sistema) e conta as chamadas."""

    def __init__(self, respostas: dict, erro: Exception | None = None):
        self.respostas, self.erro, self.chamadas = respostas, erro, []

    def gerar(self, modelo, sistema, entrada, schema, max_tokens):
        self.chamadas.append((modelo, entrada))
        if self.erro:
            raise self.erro
        chave = "classificador" if "candidatas" in sistema else "investigador" if "hipóteses" in sistema else "interprete"
        r = self.respostas[chave]
        return r(entrada) if callable(r) else r


def _ler(p):
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


@pytest.fixture
def dados_sem_regra(dados, tmp_path):
    d = tmp_path / "dados"
    shutil.copytree(dados, d)
    p = d / AURORA
    p.write_text(p.read_text(encoding="utf-8").replace("PIX ENVIADO CONTABILIDADE EXATA LTDA",
                                                       "BOLETO GRAFICA RAPIDA LTDA"), encoding="utf-8")
    return d


def _hipotese(entrada):
    ref = entrada["evidencias"][0]["ref"]
    return {"hipoteses": [{"descricao": "Hipótese de teste.", "evidencia_refs": [ref], "plausibilidade": "alta"},
                          {"descricao": "Inventada.", "evidencia_refs": ["NAO-EXISTE"], "plausibilidade": "media"}],
            "pergunta_sugerida": "Quem autorizou?", "quem_decide_sugerido": "financeiro"}


def _rodar(dados, tmp_path, cliente, nome="s"):
    res = fechar("2026-09", dados, tmp_path / nome, tmp_path / "est", cliente=cliente, cache=tmp_path / "cache")
    return res, _ler(tmp_path / nome / "pendencias.csv"), _ler(tmp_path / nome / "lancamentos_classificados.csv")


# --- modo sem IA ----------------------------------------------------------------------------------------

def test_without_ai_outputs_are_complete_and_identical_to_plain_run(dados, tmp_path):
    _rodar(dados, tmp_path, None, "sem_ia")
    fechar("2026-09", dados, tmp_path / "puro", None, cliente=None, cache=tmp_path / "cache")
    for arq in (tmp_path / "puro").iterdir():
        assert arq.read_bytes() == (tmp_path / "sem_ia" / arq.name).read_bytes(), arq.name


def test_without_credentials_there_is_no_client(monkeypatch, tmp_path):
    monkeypatch.delenv("TARVO_SEM_IA", raising=False)
    for v in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    sem_env = tmp_path / "nao_existe.env"
    assert cliente_padrao(sem_env) is None
    monkeypatch.setenv("TARVO_SEM_IA", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert cliente_padrao(sem_env) is None  # TARVO_SEM_IA vence


def test_dotenv_is_read_and_environment_wins(monkeypatch, tmp_path):
    from tarvo.agents.base import carregar_env
    monkeypatch.delenv("TARVO_TESTE_A", raising=False)
    monkeypatch.setenv("TARVO_TESTE_B", "do-ambiente")
    env = tmp_path / ".env"
    env.write_text('# comentário\nTARVO_TESTE_A="valor a"\nexport TARVO_TESTE_B=do-arquivo\nVAZIA=\n', encoding="utf-8")
    carregar_env(env)
    import os
    assert os.environ["TARVO_TESTE_A"] == "valor a" and os.environ["TARVO_TESTE_B"] == "do-ambiente"
    assert "VAZIA" not in os.environ
    monkeypatch.delenv("TARVO_TESTE_A")


# --- Classificador --------------------------------------------------------------------------------------

def test_classifier_above_threshold_is_applied_as_ia_and_leaves_the_queue(dados_sem_regra, tmp_path):
    f = Falso({"classificador": {"conta_codigo": "4.2.06", "confianca": 0.93, "justificativa": "gráfica"},
               "investigador": _hipotese})
    res, pend, lan = _rodar(dados_sem_regra, tmp_path, f)
    l53 = next(l for l in lan if l["ref_origem"] == "L53")
    assert (l53["conta_codigo"], l53["metodo"], l53["confianca"], l53["regra_id"]) == ("4.2.06", "IA", "0.93",
                                                                                      "IA-CLASSIFICADOR")
    assert all(p["ref_origem"] != "L53" for p in pend)
    rastro = _ler(tmp_path / "s" / "rastro.csv")
    assert not [r for r in rastro if r["id_saida"] == "PEN-CLASSIFICACAO_BAIXA_CONFIANCA-L53"]
    assert next(r for r in rastro if r["id_saida"] == "LAN-AUR-L53")["regra_id"] == "IA-CLASSIFICADOR"


def test_classifier_below_threshold_stays_with_a_person_with_the_proposal(dados_sem_regra, tmp_path):
    f = Falso({"classificador": {"conta_codigo": "4.2.06", "confianca": 0.55, "justificativa": "talvez"},
               "investigador": _hipotese})
    _, pend, lan = _rodar(dados_sem_regra, tmp_path, f)
    assert next(l for l in lan if l["ref_origem"] == "L53")["metodo"] == "HUMANO"
    p = next(p for p in pend if p["ref_origem"] == "L53")
    assert "IA sugere 4.2.06" in p["proposta_ia"] and "abaixo do limiar" in p["proposta_ia"]


def test_classifier_account_outside_candidates_is_discarded(dados_sem_regra, tmp_path):
    f = Falso({"classificador": {"conta_codigo": "9.9.99", "confianca": 0.99, "justificativa": "x"},
               "investigador": _hipotese})
    _, pend, lan = _rodar(dados_sem_regra, tmp_path, f)
    assert next(l for l in lan if l["ref_origem"] == "L53")["conta_codigo"] == "1.1.03.003"
    assert "descartada pelo guardrail" in next(p for p in pend if p["ref_origem"] == "L53")["proposta_ia"]


def test_candidates_are_analytic_filtered_by_sign_and_include_provisional():
    from tarvo.ingest.extrato import Lancamento
    from tarvo.ingest.plano_contas import Conta
    plano = {c: Conta(c, d, a) for c, d, a in [("4.2", "DESPESAS", False), ("4.2.06", "Serviços contábeis", True),
                                                ("3.2.01", "Rendimentos", True), ("1.1.03.003", "Adiantamentos", True),
                                                ("1.1.09.002", "Créditos não identificados", True)]}
    l = Lancamento("AURORA", "L1", date(2026, 9, 1), "BOLETO SERVICOS", D("-10.00"), "a")
    codigos = [c["codigo"] for c in classificador.candidatos(l, plano, {"credito": "1.1.09.002", "debito": "1.1.03.003"})]
    assert "4.2" not in codigos and "3.2.01" not in codigos and "1.1.03.003" in codigos and "4.2.06" in codigos


# --- Investigador ---------------------------------------------------------------------------------------

def test_investigator_fills_extra_columns_and_drops_hypotheses_with_invented_refs(dados, tmp_path):
    f = Falso({"investigador": _hipotese})
    _, pend, _ = _rodar(dados, tmp_path, f)
    l34 = next(p for p in pend if p["ref_origem"] == "L34")
    assert l34["hipoteses_ia"].startswith("1) Hipótese de teste.") and "Inventada" not in l34["hipoteses_ia"]
    assert l34["pergunta_sugerida"] == "Quem autorizou?"
    assert l34["motivo"].startswith("PIX de R$ 112.220,15")  # o motivo determinístico não muda
    roteadas = {p["tipo"] for p in pend if p["hipoteses_ia"]}
    assert roteadas == {"REPASSE_ATIPICO", "LANCAMENTO_SEM_ORIGEM", "DEVOLUCAO_PIX", "ALERTA_ANTECIPACAO"}
    assert len(f.chamadas) == 4


def test_investigator_evidence_is_built_by_code_around_the_counterparty(dados):
    from tarvo.ingest.aurora import ler_aurora
    from tarvo.ingest.orbe import ler_orbe
    from tarvo.core.rastro import LinhaRastro
    lans = ler_aurora(dados / AURORA).lancamentos
    txs = ler_orbe(dados / "01_orbe_relatorio_comissoes_set2026.csv")
    linhas = [LinhaRastro("PEN-REPASSE_ATIPICO-L34", AURORA, "L34", D("-112220.15"))]
    ent = investigador.entrada({"tipo": "REPASSE_ATIPICO", "ref_origem": "L34", "valor_brl": D("-112220.15"),
                                "motivo": "m"}, linhas, lans, txs)
    refs = {e["ref"] for e in ent["evidencias"]}
    assert {"L34", "L60"} <= refs  # o outro PIX à Atlas, dentro da janela
    assert ent["resumo_orbe_da_contraparte"]["ANTECIPACAO"]["linhas"] == 5


def test_only_valid_hypotheses_survive_the_guardrail():
    ent = {"evidencias": [{"ref": "L1"}]}
    assert investigador.validar({"hipoteses": [{"descricao": "x", "evidencia_refs": ["L9"], "plausibilidade": "alta"}],
                                 "pergunta_sugerida": "?"}, ent)[0] is None


# --- InterpreteTaxas ------------------------------------------------------------------------------------

def test_rate_interpreter_never_applies_and_checks_the_quoted_excerpt():
    ent = {"vigencia_texto": "valendo desde o carnaval de 2026", "obs": ""}
    ok = {"ambiguo": False, "vigencia_ini": "2026-02-17", "vigencia_fim": "", "confianca": 0.6,
          "trecho_que_justifica": "desde o carnaval de 2026", "pergunta": ""}
    v, _ = interprete_taxas.validar(ok, ent)
    assert v["ini"] == date(2026, 2, 17) and "Só vale depois de confirmada" in interprete_taxas.texto_proposta(v)
    assert interprete_taxas.validar({**ok, "trecho_que_justifica": "inventado"}, ent)[0] is None
    assert interprete_taxas.validar({**ok, "vigencia_fim": "2026-01-01"}, ent)[0] is None


# --- cache, teto e erros --------------------------------------------------------------------------------

def test_answers_are_cached_and_reused_without_a_client(dados, tmp_path):
    f = Falso({"investigador": _hipotese})
    _rodar(dados, tmp_path, f, "a")
    assert len(f.chamadas) == 4 and len(list((tmp_path / "cache" / "investigador").glob("*.json"))) == 4
    _rodar(dados, tmp_path, None, "b")  # sem cliente: o cache responde
    assert (tmp_path / "a" / "pendencias.csv").read_bytes() == (tmp_path / "b" / "pendencias.csv").read_bytes()


def test_call_budget_sends_the_rest_to_people(dados, tmp_path, monkeypatch):
    import tarvo.config as config
    original = config.construir_config

    def com_teto(d):
        d = {**d, "agentes": {**d["agentes"], "max_chamadas_llm": 1}}
        return original(d)
    monkeypatch.setattr("tarvo.pipeline.construir_config", com_teto)
    f = Falso({"investigador": _hipotese})
    res, pend, _ = _rodar(dados, tmp_path, f)
    assert len(f.chamadas) == 1 and sum(bool(p["hipoteses_ia"]) for p in pend) == 1
    assert sum(c.origem == "limite" for c in res.agentes.chamadas) == 3


def test_api_error_never_breaks_the_close(dados, tmp_path):
    res, pend, _ = _rodar(dados, tmp_path, Falso({}, erro=RuntimeError("503")))
    assert len(pend) == 18 and all(not p["hipoteses_ia"] for p in pend)
    assert {c.origem for c in res.agentes.chamadas} == {"erro"}


def test_cache_key_changes_with_prompt_model_or_input(tmp_path):
    class A(Agente):
        nome = "classificador"
    a, b = A("m1", None, tmp_path), A("m2", None, tmp_path)
    assert a.hash_entrada({"x": 1}) != a.hash_entrada({"x": 2}) != b.hash_entrada({"x": 1})


# --- chamada real (formato da requisição, com SDK falso) -------------------------------------------------

class _SDK:
    def __init__(self, texto='{"ok": true}', stop="end_turn"):
        self.pedidos = []
        resp = SimpleNamespace(stop_reason=stop, stop_details=None, content=[SimpleNamespace(type="text", text=texto)])
        criar = lambda **kw: (self.pedidos.append(kw), resp)[1]  # noqa: E731
        self.messages = SimpleNamespace(create=criar)
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=criar))


def _cliente(sdk):
    c = ClienteAnthropic.__new__(ClienteAnthropic)
    c.client = sdk
    return c


def test_haiku_request_uses_json_schema_and_temperature_zero():
    sdk = _SDK()
    assert _cliente(sdk).gerar("claude-haiku-4-5", "s", {"a": 1}, {"type": "object"}, 100) == {"ok": True}
    (p,) = sdk.pedidos
    assert p["extra_body"] == {"temperature": 0} and p["output_config"]["format"]["type"] == "json_schema"
    assert json.loads(p["messages"][0]["content"]) == {"a": 1}


def test_sonnet_request_uses_server_fallback_and_no_temperature():
    sdk = _SDK()
    _cliente(sdk).gerar("claude-sonnet-5-5", "s", {}, {"type": "object"}, 100)
    (p,) = sdk.pedidos
    assert p["fallbacks"] == "default" and p["betas"] == ["server-side-fallback-2026-07-01"]
    assert "extra_body" not in p and p["output_config"]["effort"] == "medium"


def test_refusal_or_truncation_is_an_error():
    for stop in ("refusal", "max_tokens"):
        with pytest.raises(RuntimeError):
            _cliente(_SDK(stop=stop)).gerar("claude-sonnet-5-5", "s", {}, {}, 10)
