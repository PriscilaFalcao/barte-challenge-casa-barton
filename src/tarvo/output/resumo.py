"""saida/resumo.md: o fechamento em linguagem do financeiro (PRD 7.9 e 15.1). Sem carimbo de data, para ser
idêntico entre execuções. Não calcula nada novo: só agrega as linhas que já estão nas 6 saídas."""
from __future__ import annotations

import collections
from decimal import Decimal

from ..core.excecoes import TipoExcecao
from ..core.money import round_money

T = TipoExcecao
ROTULO = {
    T.DIVERGENCIA_ORBE: "Orbe cobrou fora do contrato",
    T.DEVOLUCAO_LOJISTA: "Devolução ao lojista (condição não informada à Orbe)",
    T.CONTESTACAO_PONTE: "Contestação com a Ponte",
    T.COMISSAO_NAO_POSITIVA: "Comissão zero ou negativa, sem nota",
    T.SEM_CONTRATO: "Lojista sem contrato, não faturado",
    T.ALERTA_ANTECIPACAO: "Antecipação de lojista sem contrato",
    T.LANCAMENTO_SEM_ORIGEM: "Lançamento sem origem identificada",
    T.REPASSE_ATIPICO: "Repasse atípico",
    T.DEVOLUCAO_PIX: "PIX de repasse devolvido",
    T.ENTIDADE_NAO_RESOLVIDA: "Lojista não identificado",
    T.CONTRATO_AMBIGUO: "Contrato ambíguo ou ausente",
    T.CLASSIFICACAO_BAIXA_CONFIANCA: "Lançamento sem regra de classificação",
    T.CONFERIR_MES_SEGUINTE: "Conferir no mês seguinte",
    T.STATUS_PONTE_DESCONHECIDO: "Status de compliance desconhecido na Ponte",
}
_NATUREZA = {"DIVERGENCIA_CONTRATO": "divergência de contrato",
             "ISENCAO_NAO_INFORMADA_ORBE": "isenção não informada à Orbe (devolução, fora da cobrança)"}


def brl(valor: Decimal) -> str:
    """R$ em formato brasileiro, para leitura (as CSVs seguem o formato fixo com ponto decimal)."""
    v = round_money(valor)
    sinal = "−" if v < 0 else ""
    inteiro, dec = f"{abs(v):.2f}".split(".")
    return f"{sinal}R$ {int(inteiro):,}".replace(",", ".") + f",{dec}"


def _celula(texto) -> str:
    return str(texto).replace("|", "/").replace("\n", " ")


def _tabela(cabecalho: list[str], linhas: list[list]) -> list[str]:
    out = ["| " + " | ".join(cabecalho) + " |", "|" + "|".join("---" for _ in cabecalho) + "|"]
    out += ["| " + " | ".join(_celula(c) for c in l) + " |" for l in linhas]
    return out


def _agrupar(linhas: list[dict], chave) -> dict:
    grupos: dict = collections.defaultdict(list)
    for l in linhas:
        grupos[chave(l)].append(l)
    return grupos


def _ref(p: dict, nomes: dict[str, str]) -> str:
    """Pendência agrupada por lojista tem ref `<cnpj14>-<AAAAMM>`: mostra o nome junto."""
    cnpj = p["ref_origem"].split("-")[0]
    return f"{nomes[cnpj]} ({p['ref_origem']})" if cnpj in nomes else p["ref_origem"]


def gerar_resumo(mes: str, comissoes: list[dict], divergencias: list[dict], notas: list[dict],
                 lancamentos: list[dict], pendencias: list[dict], plano: dict, validacoes: str) -> str:
    mm, aaaa = mes[5:], mes[:4]
    soma = lambda xs, k: sum((x[k] for x in xs), Decimal("0"))  # noqa: E731
    chk = [c for c in comissoes if c["linha_negocio"] == "CHECKOUT"]
    rem = [c for c in comissoes if c["linha_negocio"] == "REMESSA"]
    bloqueantes = [p for p in pendencias if p["bloqueante"] == "S"]
    nomes = {c["cnpj"]: c["lojista"] for c in comissoes}
    por_metodo = collections.Counter(l["metodo"] for l in lancamentos)

    out = [f"# Fechamento Tarvo, competência {mm}/{aaaa}", "",
           "Gerado pela solução a partir dos 6 arquivos do mês. Todo número abaixo vem das CSVs de `saida/`, e cada "
           "uma delas liga ao `rastro.csv` até a linha de origem.", ""]
    situacao = ("**Pronto para fechar:** nenhuma pendência bloqueante." if not bloqueantes else
                f"**Não fechar ainda:** {len(bloqueantes)} pendência(s) bloqueante(s) mudam comissão ou nota.")
    out += [situacao, "", "## Resultado do mês", ""]
    out += _tabela(["Item", "Quantidade", "Valor"], [
        ["Comissão de checkout", f"{len(chk)} lojista(s)", brl(soma(chk, "comissao_brl"))],
        ["Comissão de remessa", f"{len(rem)} lojista(s)", brl(soma(rem, "comissao_brl"))],
        ["Notas a emitir", f"{len(notas)} nota(s)", brl(soma(notas, "valor_brl"))],
        *[[f"Divergências: {_NATUREZA.get(nat, nat)}", f"{len(ds)} transação(ões)", brl(soma(ds, "diferenca_brl"))]
          for nat, ds in sorted(_agrupar(divergencias, lambda d: d.get("natureza", "")).items())],
        ["Lançamentos classificados", f"{len(lancamentos)} ({', '.join(f'{n} {m}' for m, n in sorted(por_metodo.items()))})", ""],
        ["Pendências", f"{len(pendencias)} ({len(bloqueantes)} bloqueante(s))", ""],
    ])

    out += ["", "## Notas a emitir", ""]
    out += _tabela(["Tomador", "CNPJ", "Linha", "Valor", "Discriminação"],
                   [[n["tomador"], n["tomador_cnpj"], n["linha_negocio"], brl(n["valor_brl"]), n["discriminacao"]]
                    for n in sorted(notas, key=lambda n: (n["linha_negocio"], n["tomador"]))])

    out += ["", "## Dinheiro em jogo", "",
            "Cada pendência pelo seu valor, da maior para a menor. Os valores têm naturezas diferentes (devolução, "
            "contestação, conferência, alerta) e por isso não são somados.", ""]
    out += _tabela(["Tipo", "Referência", "Valor", "Quem decide"],
                   [[ROTULO.get(T(p["tipo"]), p["tipo"]), _ref(p, nomes), brl(p["valor_brl"]), p["quem_decide"]]
                    for p in sorted(pendencias, key=lambda p: (-abs(p["valor_brl"]), p["id_saida"]))])

    out += ["", "## Pendências por responsável", ""]
    por_pessoa: dict[str, list[dict]] = collections.defaultdict(list)
    for p in pendencias:
        por_pessoa[p["quem_decide"]].append(p)
    for pessoa, ps in sorted(por_pessoa.items()):
        out += [f"### {pessoa} ({len(ps)})", ""]
        out += _tabela(["", "Tipo", "Referência", "Valor", "Motivo"],
                       [["**bloqueante**" if p["bloqueante"] == "S" else "", ROTULO.get(T(p["tipo"]), p["tipo"]),
                         _ref(p, nomes), brl(p["valor_brl"]), p["motivo"]]
                        for p in sorted(ps, key=lambda p: (p["bloqueante"] != "S", p["tipo"], p["ref_origem"]))])
        out += [""]

    out += ["## Divergências de taxa por lojista", ""]
    div: dict[tuple, list[dict]] = collections.defaultdict(list)
    for d in divergencias:
        div[(d["linha_negocio"], d["cnpj"], d.get("natureza", ""))].append(d)
    out += _tabela(["Linha", "Lojista", "Natureza", "Transações", "Diferença líquida"],
                   [[linha, nomes.get(cnpj, cnpj), _NATUREZA.get(nat, nat), len(ds), brl(soma(ds, "diferenca_brl"))]
                    for (linha, cnpj, nat), ds in sorted(div.items())])

    out += ["", "## Classificação dos extratos", ""]
    contas: dict[tuple, list[dict]] = collections.defaultdict(list)
    for l in lancamentos:
        contas[(l["banco"], l["conta_codigo"])].append(l)
    out += _tabela(["Banco", "Conta", "Descrição", "Lançamentos", "Valor", "Método"],
                   [[banco, conta, plano[conta].descricao if conta in plano else "?", len(ls), brl(soma(ls, "valor")),
                     ", ".join(sorted({l["metodo"] for l in ls}))]
                    for (banco, conta), ls in sorted(contas.items())])

    out += ["", "## Conferência", "",
            f"- Validações antes de escrever as saídas: {validacoes}.",
            "- Linhas lidas, descartadas (rodapé, saldo, fora do mês) e avisos: `execucao.log`.",
            "- Origem de cada número: `rastro.csv` (`id_saida` → arquivo e linha de origem; a soma por `id_saida` "
            "é o número reportado).",
            "- Premissas e perguntas ao financeiro: `docs/HIPOTESES.md`.", ""]
    return "\n".join(out)
