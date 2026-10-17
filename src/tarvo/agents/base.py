"""Base dos agentes (PRD 8.2): entrada JSON mínima, saída JSON validada por schema, cache por hash.

Regras que valem para todo agente:
- O agente nunca calcula dinheiro (P2). Ele classifica, propõe ou redige; quem aplica é o código.
- A resposta fica em cache/agentes/<agente>/<hash>.json (versionado no git). Mesma entrada, mesma resposta: a
  execução é reproduzível sem chave de API, e a banca roda com o mesmo resultado que entregamos.
- Sem credencial e sem cache, o agente devolve None e a exceção fica na fila humana (modo sem IA, PRD 8.3).
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

RAIZ = Path(__file__).resolve().parent.parent.parent.parent
CACHE_PADRAO = RAIZ / "cache" / "agentes"
ENV_PADRAO = RAIZ / ".env"


def pasta_cache() -> Path:
    """cache/agentes/ do repositório, ou $TARVO_CACHE_AGENTES (testes e execuções isoladas)."""
    return Path(os.environ.get("TARVO_CACHE_AGENTES") or CACHE_PADRAO)
PROMPTS = Path(__file__).resolve().parent / "prompts"


@dataclass(frozen=True)
class Resposta:
    saida: dict | None
    origem: str  # cache | api | sem_ia | erro | limite
    hash: str
    detalhe: str = ""


class ClienteLLM(Protocol):
    def gerar(self, modelo: str, sistema: str, entrada: dict, schema: dict, max_tokens: int) -> dict: ...


def _json(v) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, default=str)


class ClienteAnthropic:
    """Chamada real. Haiku 4.5 recebe temperature=0 (via extra_body: o SDK 1.x tirou o parâmetro da assinatura,
    e o modelo ainda o aceita). Sonnet 5.5 não aceita temperature diferente do padrão; a reprodutibilidade vem
    do cache. Nos modelos 5.5 o fallback de recusa do servidor fica ligado (fallbacks="default")."""

    def __init__(self) -> None:
        import anthropic  # import tardio: sem o pacote, o sistema roda em modo sem IA

        self._anthropic = anthropic
        self.client = anthropic.Anthropic()

    def gerar(self, modelo: str, sistema: str, entrada: dict, schema: dict, max_tokens: int) -> dict:
        mensagens = [{"role": "user", "content": _json(entrada)}]
        formato = {"type": "json_schema", "schema": schema}
        if modelo.startswith("claude-haiku"):
            resp = self.client.messages.create(
                model=modelo, max_tokens=max_tokens, system=sistema, messages=mensagens,
                output_config={"format": formato}, extra_body={"temperature": 0})
        else:
            resp = self.client.beta.messages.create(
                model=modelo, max_tokens=max_tokens, system=sistema, messages=mensagens,
                output_config={"format": formato, "effort": "medium"},
                betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"recusa do modelo ({getattr(resp.stop_details, 'category', None)})")
        if resp.stop_reason == "max_tokens":
            raise RuntimeError("resposta cortada por max_tokens")
        texto = next((b.text for b in resp.content if b.type == "text"), None)
        if texto is None:
            raise RuntimeError("resposta sem bloco de texto")
        return json.loads(texto)


def carregar_env(path: Path = ENV_PADRAO) -> None:
    """Lê KEY=VALOR do .env da raiz (ignorado pelo git). O que já está no ambiente vale sobre o arquivo."""
    if not Path(path).exists():
        return
    for linha in Path(path).read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        chave, valor = chave.strip().removeprefix("export ").strip(), valor.strip().strip("'\"")
        if valor:
            os.environ.setdefault(chave, valor)


def cliente_padrao(env: Path = ENV_PADRAO) -> ClienteLLM | None:
    """None = modo sem IA: TARVO_SEM_IA=1, pacote ausente ou nenhuma credencial configurada."""
    carregar_env(env)
    if os.environ.get("TARVO_SEM_IA") == "1":
        return None
    perfil = Path.home() / ".config" / "anthropic"  # `ant auth login` grava o perfil aqui
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
            or os.environ.get("ANTHROPIC_PROFILE") or perfil.exists()):
        return None
    try:
        return ClienteAnthropic()
    except Exception:
        return None


class Agente:
    nome: str = ""
    max_tokens: int = 2048
    schema: dict = {}

    def __init__(self, modelo: str, cliente: ClienteLLM | None, cache: Path = CACHE_PADRAO) -> None:
        self.modelo = modelo
        self.cliente = cliente
        self.cache = Path(cache) / self.nome
        self.sistema = (PROMPTS / f"{self.nome}.md").read_text(encoding="utf-8")

    def hash_entrada(self, entrada: dict) -> str:
        return hashlib.sha256(_json({"agente": self.nome, "modelo": self.modelo, "sistema": self.sistema,
                                     "schema": self.schema, "entrada": entrada}).encode()).hexdigest()

    def executar(self, entrada: dict, pode_chamar: bool = True) -> Resposta:
        h = self.hash_entrada(entrada)
        arq = self.cache / f"{h[:24]}.json"
        if arq.exists():
            return Resposta(json.loads(arq.read_text(encoding="utf-8"))["saida"], "cache", h)
        if self.cliente is None:
            return Resposta(None, "sem_ia", h)
        if not pode_chamar:
            return Resposta(None, "limite", h)
        try:
            saida = self.cliente.gerar(self.modelo, self.sistema, entrada, self.schema, self.max_tokens)
        except Exception as exc:  # erro de API ou de formato: vai para a pessoa, nunca derruba o fechamento
            return Resposta(None, "erro", h, f"{type(exc).__name__}: {exc}")
        self.cache.mkdir(parents=True, exist_ok=True)
        arq.write_text(json.dumps({"agente": self.nome, "modelo": self.modelo, "entrada": entrada, "saida": saida},
                                  ensure_ascii=False, sort_keys=True, indent=2, default=str) + "\n", encoding="utf-8")
        return Resposta(saida, "api", h)
