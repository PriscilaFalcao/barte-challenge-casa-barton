"""Fechamento do mês. Hoje cobre o nível Mínimo (checkout); os demais motores entram nos próximos blocos."""
from __future__ import annotations

from pathlib import Path

from .config import carregar_defaults
from .contracts.resolver import Resolvedor
from .core.rastro import Rastro
from .engines.checkout import ResultadoCheckout, calcular_checkout
from .identity.registro import Registro
from .ingest.erros import LayoutError
from .ingest.orbe import ler_orbe
from .ingest.taxas import ARQUIVO as ARQUIVO_TAXAS
from .ingest.taxas import ler_taxas
from .output.validators import validar_i_r1
from .output.writers import escrever_csv, escrever_rastro


def _arquivo(dados: Path, padrao: str) -> Path:
    achados = sorted(dados.glob(padrao))
    if len(achados) != 1:
        raise LayoutError(f"esperava exatamente 1 arquivo {padrao} em {dados}, achei {len(achados)}")
    return achados[0]


def fechar(mes: str, dados: Path, saida: Path) -> ResultadoCheckout:
    cfg = carregar_defaults()
    contratos, excecoes_taxas = ler_taxas(_arquivo(dados, "02_*.xlsx"))
    registro = Registro.construir(contratos, cfg.ecs_extra, cfg.sem_contrato, cfg.aliases)
    txs = ler_orbe(_arquivo(dados, "01_*.csv"))

    rastro = Rastro()
    res = calcular_checkout(txs, registro, Resolvedor(contratos, cfg.overrides), mes, rastro)
    for e in excecoes_taxas:  # exceção de leitura da planilha: a linha da planilha é a origem
        rastro.add(e.id_saida, ARQUIVO_TAXAS, e.ref_origem, e.valor_brl)
    excecoes = excecoes_taxas + res.excecoes
    pendencias = [
        {"id_saida": e.id_saida, "tipo": e.tipo.value, "ref_origem": e.ref_origem,
         "valor_brl": e.valor_brl, "motivo": e.motivo, "quem_decide": e.quem_decide}
        for e in excecoes
    ]
    # Valida antes de escrever: falha de invariante não deixa saída parcial.
    validar_i_r1({"comissoes_por_lojista": res.comissoes, "pendencias": pendencias}, rastro)

    saida.mkdir(parents=True, exist_ok=True)
    escrever_csv(saida / "comissoes_por_lojista.csv", "comissoes_por_lojista", res.comissoes)
    escrever_csv(saida / "pendencias.csv", "pendencias", pendencias)
    escrever_rastro(saida / "rastro.csv", rastro)
    return res
