"""Construtores sintéticos compartilhados pelos testes dos motores."""
from datetime import date
from decimal import Decimal as D

from tarvo.contracts.resolver import Resolvedor
from tarvo.core.rastro import Rastro
from tarvo.engines.checkout import calcular_checkout
from tarvo.identity.registro import Registro
from tarvo.ingest.orbe import OrbeTx
from tarvo.ingest.taxas import ContratoLinha

CNPJ = "11111111000111"
EC = "1000000001"


def contrato(cnpj=CNPJ, ec=EC, ini=None, fim=None, ref="Taxas!L6", debito="1.00", antecip="2.00", nome="Loja Um"):
    taxas = {"DEBITO": D(debito), "CREDITO_1X": D("2.50"), "CREDITO_2_6X": D("3.00"),
             "CREDITO_7_12X": D("3.50"), "PIX": D("0.90"), "ANTECIPACAO": D(antecip)}
    return ContratoLinha(ref, nome, cnpj, ec, taxas, None, "x", ini, fim, True, None)


def tx(id_="TX1", dia=date(2026, 9, 10), tipo="VENDA", mod="DEBITO", parc=1, bruto="100.00",
       valor_taxa="99.99", ref=None, orig=None, ec=EC, aplicada="9.99"):
    return OrbeTx(id_, dia, ec, "NOME", tipo, mod, parc, "VISA", D(bruto), D(aplicada), D(valor_taxa),
                  D(bruto), ref, orig)


def rodar_checkout(txs, contratos=None, overrides=(), sem_contrato=None, ecs_extra=None, mes="2026-09"):
    contratos = contratos or [contrato()]
    reg = Registro.construir(contratos, ecs_extra or {}, sem_contrato or {})
    rastro = Rastro()
    res = calcular_checkout(txs, reg, Resolvedor(contratos, overrides), mes, rastro)
    return res, rastro
