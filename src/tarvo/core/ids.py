"""Normalização de CNPJ e geração determinística de id_saida (PRD seção 6)."""
from __future__ import annotations

import re

_LINHA = {"CHECKOUT": "CHK", "REMESSA": "REM"}
_BANCO = {"AURORA": "AUR", "MERIDIANO": "MER"}


def norm_cnpj(valor: str | int) -> str:
    """Só dígitos, completado com zeros à esquerda até 14."""
    digitos = re.sub(r"\D", "", str(valor))
    if not digitos or len(digitos) > 14:
        raise ValueError(f"CNPJ inválido: {valor!r}")
    return digitos.zfill(14)


def _competencia(mes: str) -> str:
    return mes.replace("-", "")


def _linha(linha: str) -> str:
    if linha not in _LINHA:
        raise ValueError(f"linha_negocio inválida: {linha!r}")
    return _LINHA[linha]


def id_comissao(linha: str, cnpj14: str, mes: str) -> str:
    return f"COM-{_linha(linha)}-{cnpj14}-{_competencia(mes)}"


def id_divergencia(linha: str, ref_origem: str) -> str:
    return f"DIV-{_linha(linha)}-{ref_origem}"


def id_nota_checkout(cnpj14: str, mes: str) -> str:
    return f"NF-CHK-{cnpj14}-{_competencia(mes)}"


def id_nota_remessa(mes: str) -> str:
    return f"NF-REM-{_competencia(mes)}"


def id_lancamento(banco: str, ref_origem: str) -> str:
    if banco not in _BANCO:
        raise ValueError(f"banco inválido: {banco!r}")
    return f"LAN-{_BANCO[banco]}-{ref_origem}"


def id_pendencia(tipo: str, ref_origem: str) -> str:
    return f"PEN-{tipo}-{ref_origem}"
