"""Motor de notas (PRD 7.6): quais notas emitir, para quem e por quanto, a partir das comissões."""
from __future__ import annotations

import collections
from dataclasses import dataclass, field
from decimal import Decimal

from ..core.excecoes import Excecao, TipoExcecao
from ..core.ids import id_nota_checkout, id_nota_remessa
from ..core.money import fmt
from ..core.rastro import LinhaRastro, Rastro

# ✅ N3: tomador único da nota de remessa.
PONTE_CNPJ = "75374179000146"
PONTE_NOME = "Ponte Câmbio S.A."

# ✅ N4: discriminação é texto livre; usamos template fixo (serviço + competência), sem IA.
_TEMPLATE = {
    "CHECKOUT": "Comissão sobre serviços de checkout, competência {mm}/{aaaa}",
    "REMESSA": "Comissão sobre serviços de intermediação de remessa internacional, competência {mm}/{aaaa}",
}


@dataclass
class ResultadoNotas:
    notas: list[dict] = field(default_factory=list)
    excecoes: list[Excecao] = field(default_factory=list)


def _copiar(rastro: Rastro, origem: list[LinhaRastro], id_destino: str, so_nao_zero: bool = False) -> None:
    linhas = [l for l in origem if l.valor != 0] if so_nao_zero else origem
    for l in linhas or origem:  # tudo zero: sem linha que "motive", copia todas para o rastro não ficar vazio
        rastro.add(id_destino, l.arquivo_origem, l.ref_origem, l.valor, l.componente, l.taxa_usada_pct, l.regra_id)


def _nao_positiva(res: ResultadoNotas, rastro: Rastro, ref: str, valor: Decimal, motivo: str,
                  origem: list[LinhaRastro]) -> None:
    exc = Excecao.nova(TipoExcecao.COMISSAO_NAO_POSITIVA, ref, valor, motivo)
    res.excecoes.append(exc)
    _copiar(rastro, origem, exc.id_saida, so_nao_zero=True)


def calcular_notas(comissoes: list[dict], rastro: Rastro, mes: str) -> ResultadoNotas:
    """✅ N1: checkout = 1 nota por lojista, tomador = lojista. ✅ N2: valor zero ou negativo não emite,
    não passa para o mês seguinte e vira pendência da Helena. ✅ N3: remessa = 1 nota para a Ponte, pelo
    total. Atlas não tem comissão, então não tem nota (✅ C9). As linhas de rastro da nota são as mesmas
    das comissões que a compõem."""
    aaaa, mm = mes.split("-")
    competencia = f"{aaaa}{mm}"
    res = ResultadoNotas()
    por_id: dict[str, list[LinhaRastro]] = collections.defaultdict(list)
    for l in rastro.linhas():
        por_id[l.id_saida].append(l)

    for c in sorted((c for c in comissoes if c["linha_negocio"] == "CHECKOUT"), key=lambda c: c["id_saida"]):
        valor, origem = c["comissao_brl"], por_id[c["id_saida"]]
        if valor <= 0:
            _nao_positiva(res, rastro, f"{c['cnpj']}-{competencia}", valor,
                          f"Comissão de checkout de {c['lojista']} em {mm}/{aaaa} é R$ {fmt(valor)}: sem nota. "
                          f"O valor não passa para o mês seguinte; tratar com o lojista.", origem)
            continue
        id_nota = id_nota_checkout(c["cnpj"], mes)
        res.notas.append({
            "id_saida": id_nota, "tomador_cnpj": c["cnpj"], "tomador": c["lojista"],
            "linha_negocio": "CHECKOUT", "valor_brl": valor,
            "discriminacao": _TEMPLATE["CHECKOUT"].format(mm=mm, aaaa=aaaa),
        })
        _copiar(rastro, origem, id_nota)

    remessa = [c for c in comissoes if c["linha_negocio"] == "REMESSA"]
    if remessa:
        total = sum((c["comissao_brl"] for c in remessa), Decimal("0"))
        origem = [l for c in sorted(remessa, key=lambda c: c["id_saida"]) for l in por_id[c["id_saida"]]]
        if total <= 0:
            _nao_positiva(res, rastro, f"REMESSA-{competencia}", total,
                          f"Comissão total de remessa em {mm}/{aaaa} é R$ {fmt(total)}: sem nota para a Ponte.",
                          origem)
        else:
            id_nota = id_nota_remessa(mes)
            res.notas.append({
                "id_saida": id_nota, "tomador_cnpj": PONTE_CNPJ, "tomador": PONTE_NOME,
                "linha_negocio": "REMESSA", "valor_brl": total,
                "discriminacao": _TEMPLATE["REMESSA"].format(mm=mm, aaaa=aaaa),
            })
            _copiar(rastro, origem, id_nota)
    res.excecoes.sort(key=lambda e: e.id_saida)
    return res
