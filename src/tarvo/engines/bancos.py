"""Motor de classificação bancária (PRD 7.7): cada lançamento dos dois extratos ganha uma conta analítica.

Ordem de decisão: (1) REGRA de `regras_lancamento` (primeira que casa, confiança 1); (2) a regra pode abrir
pendência quando a contrapartida depende de alguém (PIX sem identificação, devolução); (3) sem regra, conta
provisória, metodo HUMANO, confiança 0 e pendência. No B8 o agente Classificador entra antes do passo 3.

Conciliações determinísticas, sem IA:
- TED de liquidação à Ponte = Σ(Valor R$ + IOF) das operações contratadas no dia (21 de 21 em setembro).
- Transferência Aurora → Meridiano pareada pelo valor com a TED de mesma titularidade no Meridiano; a que não
  tem par no mês vira conferência no mês seguinte (✅ L92: sai em 30/09, cai em 01/10).
"""
from __future__ import annotations

import collections
from dataclasses import dataclass, field
from decimal import Decimal

from ..config import AlertaLancamento, RegraLancamento
from ..core.competencia import no_mes
from ..core.excecoes import Excecao, TipoExcecao
from ..core.ids import id_lancamento
from ..core.ledger import Ledger
from ..core.money import fmt
from ..core.rastro import Rastro
from ..ingest.erros import LayoutError
from ..ingest.extrato import Lancamento
from ..ingest.plano_contas import Conta
from ..ingest.ponte import OpPonte
from ..ingest.texto import norm_texto

REGRA_TED_PONTE = "MER-TED-PONTE"
REGRA_PIX_LOJISTA = "MER-PIX-LOJISTA"
REGRA_TRANSF_SAIDA = "AUR-TRANSF-MER"
REGRA_TRANSF_ENTRADA = "MER-TED-TARVO"
SEM_REGRA = "SEM-REGRA"
DECISAO = "DECISAO-HUMANA"
UM, ZERO = Decimal("1.00"), Decimal("0.00")


@dataclass
class ResultadoBancos:
    lancamentos: list[dict] = field(default_factory=list)
    excecoes: list[Excecao] = field(default_factory=list)
    conciliadas: int = 0  # TEDs à Ponte que bateram com as operações do dia
    # Σ PIX recebidos de lojistas + Σ TEDs à Ponte no mês: o que ficou de recursos para remessas sem liquidar.
    # 📄 Setembro: exatamente R$ 18.240,00, o adiantamento da Ponte Aérea. Por lojista os PIX não batem.
    saldo_recursos_remessa: Decimal = Decimal("0")


def _validar_contas(plano: dict[str, Conta], regras: tuple[RegraLancamento, ...],
                    provisoria: dict[str, str]) -> None:
    """Conta de regra que não existe ou é sintética derruba a execução antes de classificar (I-C1, P9)."""
    destinos = [(f"regra {r.id}", r.conta) for r in regras] + [(f"conta provisória {k}", v)
                                                               for k, v in provisoria.items()]
    if set(provisoria) != {"credito", "debito"}:
        raise LayoutError("conta_provisoria precisa ter 'credito' e 'debito'")
    for onde, conta in destinos:
        if conta not in plano or not plano[conta].analitica:
            raise LayoutError(f"{onde}: conta {conta} não existe no plano ou não aceita lançamento")


def _regra_de(l: Lancamento, regras: tuple[RegraLancamento, ...]) -> RegraLancamento | None:
    texto = norm_texto(l.descricao)
    sinal = "credito" if l.valor > 0 else "debito"
    return next((r for r in regras
                 if r.banco == l.banco and r.sinal in (None, sinal) and r.padrao.search(texto)), None)


def _fmt_motivo(modelo: str, l: Lancamento) -> str:
    return modelo.format(data=l.data.strftime("%d/%m/%Y"), valor=fmt(abs(l.valor)), descricao=l.descricao,
                         ref=l.ref_origem)


def classificar_lancamentos(
    lancamentos: list[Lancamento], plano: dict[str, Conta], regras: tuple[RegraLancamento, ...],
    conta_provisoria: dict[str, str], alertas: tuple[AlertaLancamento, ...], ops_ponte: list[OpPonte],
    mes: str, rastro: Rastro, ledger: Ledger | None = None, decisoes_conta: dict[str, str] | None = None,
) -> ResultadoBancos:
    """`decisoes_conta`: ref_origem -> conta decidida por uma pessoa na fila (escopo "só neste caso"). Vale sobre
    a regra: metodo HUMANO, confiança 1, sem pendência de classificação (PRD 8.4, passo 3)."""
    decisoes_conta = decisoes_conta or {}
    _validar_contas(plano, regras, conta_provisoria)
    for ref, conta in decisoes_conta.items():
        if conta not in plano or not plano[conta].analitica:
            raise LayoutError(f"decisão para {ref}: conta {conta} não existe no plano ou não aceita lançamento")
    res = ResultadoBancos()

    def pendencia(tipo: TipoExcecao, l: Lancamento, motivo: str, regra_id: str) -> None:
        exc = Excecao.nova(tipo, l.ref_origem, l.valor, motivo)
        res.excecoes.append(exc)
        rastro.add(exc.id_saida, l.arquivo, l.ref_origem, l.valor, "", "", regra_id)

    do_mes = []
    for l in sorted(lancamentos, key=lambda l: (l.banco, l.data, l.ref_origem)):
        if no_mes(l.data, mes):
            do_mes.append(l)
        elif ledger is not None:
            ledger.ignorar(l.banco.capitalize(), "fora do mês", l.ref_origem)

    # Σ(Valor R$ + IOF) das operações da Ponte por data de contratação, com a duplicata contada uma vez (✅ R6).
    unicas = {o.n_operacao: o for o in sorted(ops_ponte, key=lambda o: (o.n_operacao, o.linha_fisica), reverse=True)}
    liquidacao_dia: dict = collections.defaultdict(Decimal)
    for o in unicas.values():
        if o.valor_brl is not None:
            liquidacao_dia[o.data_contratacao] += o.valor_brl + (o.iof or Decimal("0"))

    classificados: list[tuple[Lancamento, RegraLancamento | None]] = []
    recursos: list[Lancamento] = []  # PIX de lojistas e TEDs à Ponte: formam o saldo de recursos para remessas
    for l in do_mes:
        regra = _regra_de(l, regras)
        classificados.append((l, regra))
        if l.ref_origem in decisoes_conta:
            conta, metodo, confianca, regra_id = decisoes_conta[l.ref_origem], "HUMANO", UM, DECISAO
            if regra is not None and regra.pendencia_tipo is not None:  # a decisão é da conta, não do motivo
                pendencia(regra.pendencia_tipo, l, _fmt_motivo(regra.pendencia_motivo, l), regra.id)
        elif regra is None:
            conta = conta_provisoria["credito" if l.valor > 0 else "debito"]
            metodo, confianca, regra_id = "HUMANO", ZERO, SEM_REGRA
            pendencia(TipoExcecao.CLASSIFICACAO_BAIXA_CONFIANCA, l,
                      f"Nenhuma regra reconhece '{l.descricao}' ({l.banco}, {l.data.strftime('%d/%m/%Y')}, "
                      f"R$ {fmt(l.valor)}). Lançado provisoriamente em {conta} ({plano[conta].descricao}); "
                      f"definir a conta e, se for recorrente, criar a regra.", SEM_REGRA)
        else:
            conta, metodo, confianca, regra_id = regra.conta, "REGRA", UM, regra.id
            if regra.pendencia_tipo is not None:
                pendencia(regra.pendencia_tipo, l, _fmt_motivo(regra.pendencia_motivo, l), regra.id)
            if regra.id == REGRA_TED_PONTE:
                esperado = liquidacao_dia.get(l.data, Decimal("0"))
                if esperado == -l.valor:
                    res.conciliadas += 1
                else:
                    pendencia(TipoExcecao.LANCAMENTO_SEM_ORIGEM, l,
                              f"TED de liquidação à Ponte de R$ {fmt(-l.valor)} em {l.data.strftime('%d/%m/%Y')} "
                              f"não bate com Σ(Valor R$ + IOF) das operações contratadas no dia "
                              f"(R$ {fmt(esperado)}). Conferir com a Ponte.", regra.id)
        id_saida = id_lancamento(l.banco, l.ref_origem)
        res.lancamentos.append({
            "id_saida": id_saida, "banco": l.banco, "ref_origem": l.ref_origem, "data": l.data,
            "descricao": l.descricao, "valor": l.valor, "conta_codigo": conta, "metodo": metodo,
            "confianca": confianca, "regra_id": regra_id,
        })
        rastro.add(id_saida, l.arquivo, l.ref_origem, l.valor, "", "", regra_id)
        if regra_id in (REGRA_PIX_LOJISTA, REGRA_TED_PONTE):
            res.saldo_recursos_remessa += l.valor
            recursos.append(l)

    _parear_transferencias(classificados, pendencia)
    _saldo_recursos_remessa(res, recursos, mes, rastro, pendencia)
    _aplicar_alertas(do_mes, alertas, mes, pendencia)
    res.excecoes.sort(key=lambda e: e.id_saida)
    return res


def _parear_transferencias(classificados, pendencia) -> None:
    saidas = [l for l, r in classificados if r is not None and r.id == REGRA_TRANSF_SAIDA]
    entradas = [l for l, r in classificados if r is not None and r.id == REGRA_TRANSF_ENTRADA]
    livres = sorted(entradas, key=lambda l: (l.data, l.ref_origem))
    sem_par = []
    for s in sorted(saidas, key=lambda l: (l.data, l.ref_origem)):
        par = next((e for e in livres if e.valor == -s.valor and e.data >= s.data), None)
        if par is None:
            sem_par.append(s)
        else:
            livres.remove(par)
    for s in sem_par:
        pendencia(TipoExcecao.CONFERIR_MES_SEGUINTE, s,
                  f"Transferência de R$ {fmt(-s.valor)} para o Meridiano em {s.data.strftime('%d/%m/%Y')} sem crédito "
                  f"correspondente no extrato do Meridiano deste mês. Fica em Transferências entre contas próprias; "
                  f"conferir que cai no Meridiano no início do mês seguinte.", REGRA_TRANSF_SAIDA)
    for e in livres:
        pendencia(TipoExcecao.LANCAMENTO_SEM_ORIGEM, e,
                  f"TED de mesma titularidade de R$ {fmt(e.valor)} em {e.data.strftime('%d/%m/%Y')} sem transferência "
                  f"correspondente no Aurora deste mês. Pode ser a transferência do fim do mês anterior: conferir "
                  f"com a pendência de conferência do mês anterior.", REGRA_TRANSF_ENTRADA)


def _saldo_recursos_remessa(res: ResultadoBancos, recursos: list[Lancamento], mes: str, rastro: Rastro,
                            pendencia) -> None:
    """Σ PIX recebidos de lojistas + Σ TEDs à Ponte (negativas) no mês. Sobra de PIX = remessa que sai no mês
    seguinte (✅ Helena, resposta ao Mateus: "dinheiro de uma remessa que ainda não foi feita"); falta = TED
    liquidando recursos recebidos antes. Nos dois casos fica no passivo e vira conferência, sem alterar comissão.
    Se um único PIX explica a sobra, a pendência aponta para ele (FITID); senão, para o conjunto."""
    saldo = res.saldo_recursos_remessa
    if saldo == 0:
        return
    if saldo > 0:
        unicos = [l for l in recursos if l.valor == saldo and l.valor > 0]
        if len(unicos) == 1:
            (l,) = unicos
            pendencia(TipoExcecao.CONFERIR_MES_SEGUINTE, l,
                      f"PIX de R$ {fmt(saldo)} em {l.data.strftime('%d/%m/%Y')} ({l.descricao}) sem operação da "
                      f"Ponte que o explique: é a sobra de PIX de lojistas sobre as TEDs à Ponte no mês. Pelo "
                      f"critério do financeiro, é dinheiro de remessa que sai no mês seguinte. Fica em Recursos de "
                      f"lojistas para remessas; conferir a operação no relatório da Ponte do mês seguinte.",
                      REGRA_PIX_LOJISTA)
            return
        motivo = (f"PIX de lojistas superam as TEDs à Ponte em R$ {fmt(saldo)} no mês e nenhum PIX isolado "
                  f"explica a sobra. Provável remessa que sai no mês seguinte; fica em Recursos de lojistas para "
                  f"remessas. Conferir no relatório da Ponte do mês seguinte.")
    else:
        motivo = (f"TEDs à Ponte superam os PIX de lojistas em R$ {fmt(-saldo)} no mês: provável liquidação de "
                  f"recursos recebidos no mês anterior (conferir com a pendência de conferência do mês anterior).")
    exc = Excecao.nova(TipoExcecao.CONFERIR_MES_SEGUINTE, f"RECURSOS-REMESSAS-{mes.replace('-', '')}", saldo, motivo)
    res.excecoes.append(exc)
    for l in recursos:
        rastro.add(exc.id_saida, l.arquivo, l.ref_origem, l.valor, "", "", "SALDO-REMESSAS")


def _aplicar_alertas(do_mes: list[Lancamento], alertas: tuple[AlertaLancamento, ...], mes: str, pendencia) -> None:
    por_ref = {(l.banco, l.ref_origem): l for l in do_mes}
    for a in alertas:
        if a.mes != mes:
            continue
        l = por_ref.get((a.banco, a.ref))
        if l is None or (l.data, l.valor) != (a.data, a.valor):
            raise LayoutError(f"alerta de lançamento {a.banco} {a.ref} ({a.data}, R$ {fmt(a.valor)}) não casa com "
                              f"o extrato de {mes}; revisar alertas_lancamento")
        pendencia(a.tipo, l, a.motivo, "ALERTA")
