"""Checkpoint por etapa (PRD 3 e 15.10): cada etapa grava o seu resultado com um fingerprint de tudo o que
ela lê. Na execução seguinte, fingerprint igual reaproveita o resultado; diferente, a etapa roda de novo.

O fingerprint inclui o código da solução, o conteúdo dos arquivos de entrada, o trecho da configuração que a
etapa usa, as decisões que ela aplica e os fingerprints das etapas de que depende. Não existe invalidação
manual: o que mudou muda o fingerprint, então um resultado velho nunca é reaproveitado por engano.
"""
from __future__ import annotations

import hashlib
import json
import pickle
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent  # src/tarvo


def _hash(*partes) -> str:
    h = hashlib.sha256()
    for p in partes:
        h.update(p if isinstance(p, bytes) else json.dumps(p, ensure_ascii=False, sort_keys=True, default=str).encode())
        h.update(b"\x00")
    return h.hexdigest()


def hash_codigo() -> str:
    """Qualquer mudança no código da solução invalida todos os checkpoints."""
    arquivos = sorted(_SRC.rglob("*.py"))
    return _hash(*[str(a.relative_to(_SRC)).encode() + b"\x00" + a.read_bytes() for a in arquivos])


def hash_arquivo(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprint(etapa: str, *partes) -> str:
    return _hash(etapa, *partes)


class Checkpoints:
    """Guarda em <pasta>/<mes>/<etapa>.pkl o par (fingerprint, resultado)."""

    def __init__(self, pasta: Path | None, mes: str):
        self.pasta = Path(pasta) / "execucoes" / mes if pasta is not None else None

    def carregar(self, etapa: str, fp: str):
        if self.pasta is None:
            return None
        arq = self.pasta / f"{etapa}.pkl"
        if not arq.exists():
            return None
        try:
            salvo_fp, resultado = pickle.loads(arq.read_bytes())
        except Exception:  # checkpoint corrompido ou de outra versão: recalcula
            return None
        return resultado if salvo_fp == fp else None

    def salvar(self, etapa: str, fp: str, resultado) -> None:
        if self.pasta is None:
            return
        self.pasta.mkdir(parents=True, exist_ok=True)
        tmp = self.pasta / f"{etapa}.pkl.tmp"
        tmp.write_bytes(pickle.dumps((fp, resultado)))
        tmp.replace(self.pasta / f"{etapa}.pkl")
