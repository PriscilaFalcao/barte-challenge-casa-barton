"""Fechamento do mês em etapas com checkpoint (PRD 3, 7 e 8).

Etapas, na ordem: ingestao -> checkout -> divergencias -> remessa -> notas -> bancos -> agentes -> consolidacao.
As seis primeiras gravam checkpoint (estado/checkpoint.py): fingerprint igual, o resultado é reaproveitado.
Uma decisão de conta, por exemplo, muda só o fingerprint de `bancos`; checkout, remessa e notas são lidos do
checkpoint. `agentes` (o orquestrador, com cache próprio por hash) e `consolidacao` (validação e escrita) rodam
sempre. Cada etapa grava um evento no estado (data/tarvo.db), que a interface (B9) mostra ao vivo.

Sem pasta de estado (`estado=None`) o fechamento roda puro, sem checkpoint nem fila: é o mesmo cálculo.
"""
from __future__ import annotations

import collections
import time
from dataclasses import dataclass, field
from pathlib import Path

from .agents.base import ClienteLLM, cliente_padrao, pasta_cache
from .agents.orquestrador import Contexto, ResultadoAgentes, orquestrar
from .config import construir_config, ler_yaml, mesclar_promovidas
from .contracts.resolver import Resolvedor
from .core.competencia import no_mes
from .core.excecoes import Excecao, TipoExcecao
from .core.ledger import Ledger
from .core.money import fmt
from .core.rastro import LinhaRastro, Rastro
from .engines.bancos import classificar_lancamentos
from .engines.checkout import calcular_checkout
from .engines.divergencias import calcular_divergencias
from .engines.notas import calcular_notas
from .engines.remessa import calcular_remessa
from .estado.checkpoint import Checkpoints, fingerprint, hash_arquivo, hash_codigo
from .estado.db import Estado
from .identity.registro import Registro
from .ingest.aurora import ler_aurora
from .ingest.erros import LayoutError
from .ingest.extrato import Extrato
from .ingest.meridiano import ler_meridiano
from .ingest.orbe import Substituicao, ler_orbe, unir_orbe
from .ingest.plano_contas import ler_planos
from .ingest.ponte import ler_ponte
from .ingest.taxas import ler_taxas
from .output.resumo import gerar_resumo
from .output.validators import validar_i_c1, validar_i_d1, validar_i_n1, validar_i_r1, validar_i_r2, validar_i_r3
from .output.writers import escrever_csv, escrever_rastro

# Cada fonte pode vir em mais de um arquivo no mês (padrões por prefixo, ordenados pelo nome). Na Orbe, o 01 é o
# relatório e o 06 são os ajustes tardios, no mesmo formato; os dois entram juntos (ingest.orbe.unir_orbe).
ARQUIVOS = {"orbe": ("01_*.csv", "06_*.csv"), "taxas": ("02_*.xlsx",), "ponte": ("03_*.eml",),
            "plano": ("04_*.csv",), "aurora": ("05a_*.csv",), "meridiano": ("05b_*.ofx",)}
COLUNAS_IA = ("hipoteses_ia", "pergunta_sugerida", "proposta_ia", "decisao")  # extras sempre presentes


@dataclass
class ResultadoFechamento:
    comissoes: list[dict]
    divergencias: list[dict]
    excecoes: list
    notas: list[dict]
    lancamentos: list[dict]
    etapas: list[tuple[str, str]] = field(default_factory=list)  # (etapa, executada | reaproveitada)
    agentes: ResultadoAgentes | None = None
    execucao_id: int | None = None


@dataclass
class Ingestao:
    nomes: dict[str, str]
    contratos: list
    excecoes_taxas: list
    txs: list
    ops: list
    plano: dict
    aurora: object
    meridiano: object
    ledger: Ledger
    rastro: Rastro  # linhas das exceções de leitura da planilha e das trocas de linha da Orbe
    excecoes_orbe: list = field(default_factory=list)  # uma por id_transacao que apareceu em mais de um arquivo
    trocas_orbe: list[Substituicao] = field(default_factory=list)
    refs_taxas: dict[str, set] = field(default_factory=dict)  # arquivo de taxas -> refs de linha (I-R2)
    n_arquivos: dict[str, int] = field(default_factory=dict)  # fonte -> quantos arquivos foram lidos


@dataclass
class Saida:
    """Resultado de uma etapa de cálculo: o objeto do motor, as linhas de rastro e o que ela descartou."""
    resultado: object
    rastro: Rastro
    ledger: Ledger = field(default_factory=Ledger)


def _arquivos(dados: Path, padroes: tuple[str, ...]) -> list[Path]:
    achados = sorted({p for padrao in padroes for p in dados.glob(padrao)}, key=lambda p: p.name)
    if not achados:
        raise LayoutError(f"esperava ao menos 1 arquivo {' ou '.join(padroes)} em {dados}, achei 0")
    return achados


def _juntar_extratos(extratos: list) -> Extrato:
    """Vários extratos da mesma conta: os lançamentos se somam; a cadeia de saldos é conferida em cada arquivo."""
    if len(extratos) == 1:
        return extratos[0]
    return Extrato([l for e in extratos for l in e.lancamentos], extratos[0].saldo_inicial, extratos[-1].saldo_final)


def checar_mes_com_dados(n_orbe_mes: int, n_ponte_mes: int, mes: str) -> list[str]:
    """Mês errado não pode gerar saídas vazias que parecem válidas. Devolve avisos (uma fonte vazia)."""
    if n_orbe_mes == 0 and n_ponte_mes == 0:
        raise LayoutError(f"nenhuma linha da Orbe nem da Ponte cai em {mes}; os arquivos são de outro mês?")
    avisos = []
    if n_orbe_mes == 0:
        avisos.append(f"Orbe: nenhuma linha em {mes}")
    if n_ponte_mes == 0:
        avisos.append(f"Ponte: nenhuma operação em {mes}")
    return avisos


# --- etapas de cálculo (funções puras: mesma entrada, mesma saída) ------------------------------------------

def _excecao_troca(t: Substituicao) -> Excecao:
    d, m = t.descartada, t.mantida
    return Excecao.nova(
        TipoExcecao.LINHA_ORBE_SUBSTITUIDA, d.id_transacao, d.valor_bruto,
        f"O id_transacao {d.id_transacao} aparece em {d.arquivo} (movimento {d.data_movimento:%d/%m/%Y}, bruto "
        f"R$ {fmt(d.valor_bruto)}, taxa R$ {fmt(d.valor_taxa)}) e em {m.arquivo} (movimento "
        f"{m.data_movimento:%d/%m/%Y}, bruto R$ {fmt(m.valor_bruto)}, taxa R$ {fmt(m.valor_taxa)}). Premissa: a "
        f"linha mais recente permanece e a mais antiga sai; o cálculo usa a de {m.arquivo}. Confirmar com a Helena.")


def _ingerir(arqs: dict[str, list[Path]]) -> Ingestao:
    ledger = Ledger()
    rastro = Rastro()
    contratos, excecoes_taxas, refs_taxas = [], [], {}
    for p in arqs["taxas"]:
        linhas, excecoes = ler_taxas(p, ledger)
        contratos += linhas
        excecoes_taxas += excecoes
        refs_taxas[p.name] = {c.ref_origem for c in linhas}
        for e in excecoes:  # exceção de leitura da planilha: a linha da planilha é a origem
            rastro.add(e.id_saida, p.name, e.ref_origem, e.valor_brl)
    orbe = [ler_orbe(p, p.name) for p in arqs["orbe"]]
    txs, trocas = unir_orbe(orbe[0], orbe[1:])
    excecoes_orbe = [_excecao_troca(t) for t in trocas]
    for e, t in zip(excecoes_orbe, trocas):  # a origem da exceção é a linha que saiu
        rastro.add(e.id_saida, t.descartada.arquivo, t.descartada.id_transacao, e.valor_brl)
    ops = [o for p in arqs["ponte"] for o in ler_ponte(p, ledger, p.name)]
    meridiano = _juntar_extratos([ler_meridiano(p, p.name) for p in arqs["meridiano"]])
    fitids: dict[str, str] = {}
    for l in meridiano.lancamentos:
        if fitids.setdefault(l.ref_origem, l.arquivo) != l.arquivo:
            raise LayoutError(f"Meridiano: FITID {l.ref_origem} em {fitids[l.ref_origem]} e em {l.arquivo}; "
                              f"os extratos se sobrepõem?")
    return Ingestao({k: ", ".join(p.name for p in v) for k, v in arqs.items()}, contratos, excecoes_taxas, txs,
                    ops, ler_planos(arqs["plano"]),
                    _juntar_extratos([ler_aurora(p, ledger, p.name) for p in arqs["aurora"]]), meridiano, ledger,
                    rastro, excecoes_orbe, trocas, refs_taxas, {k: len(v) for k, v in arqs.items()})


def _registro(ing: Ingestao, cfg) -> Registro:
    return Registro.construir(ing.contratos, cfg.ecs_extra, cfg.sem_contrato, cfg.aliases)


def _checkout(ing: Ingestao, cfg, mes: str) -> Saida:
    r, l = Rastro(), Ledger()
    res = calcular_checkout(ing.txs, _registro(ing, cfg), Resolvedor(ing.contratos, cfg.overrides), mes, r, l)
    return Saida(res, r, l)


def _divergencias(chk: Saida, mes: str) -> Saida:
    r = Rastro()
    res = chk.resultado
    return Saida(calcular_divergencias(res.linhas, r, mes, {c["cnpj"]: c["lojista"] for c in res.comissoes}), r)


def _remessa(ing: Ingestao, cfg, mes: str) -> Saida:
    r, l = Rastro(), Ledger()
    res = calcular_remessa(ing.ops, _registro(ing, cfg), Resolvedor(ing.contratos, cfg.overrides), mes, r, ledger=l)
    return Saida(res, r, l)


def _notas(chk: Saida, rem: Saida, mes: str) -> Saida:
    # A nota copia as linhas de rastro das comissões; só as linhas novas pertencem a esta etapa.
    r = Rastro.de(chk.rastro.linhas() + rem.rastro.linhas())
    n0 = len(r.linhas())
    res = calcular_notas(chk.resultado.comissoes + rem.resultado.comissoes, r, mes)
    return Saida(res, Rastro.de(r.linhas()[n0:]))


def _bancos(ing: Ingestao, cfg, mes: str, decisoes_conta: dict[str, str]) -> Saida:
    r, l = Rastro(), Ledger()
    res = classificar_lancamentos(ing.aurora.lancamentos + ing.meridiano.lancamentos, ing.plano,
                                  cfg.regras_lancamento, cfg.conta_provisoria, cfg.alertas_lancamento, ing.ops,
                                  mes, r, l, decisoes_conta)
    return Saida(res, r, l)


class _Executor:
    """Roda uma etapa com checkpoint e grava o evento correspondente."""

    def __init__(self, ck: Checkpoints, estado: Estado | None, execucao_id: int | None):
        self.ck, self.estado, self.execucao_id = ck, estado, execucao_id
        self.etapas: list[tuple[str, str]] = []

    def evento(self, etapa: str, status: str, t0: float, detalhe: dict | None = None) -> None:
        self.etapas.append((etapa, status))
        if self.estado is not None:
            self.estado.evento(self.execucao_id, len(self.etapas), etapa, status,
                               int((time.perf_counter() - t0) * 1000), detalhe)

    def rodar(self, etapa: str, fp: str, funcao, contagens=lambda r: {}):
        t0 = time.perf_counter()
        resultado = self.ck.carregar(etapa, fp)
        status = "reaproveitada"
        if resultado is None:
            resultado = funcao()
            self.ck.salvar(etapa, fp, resultado)
            status = "executada"
        self.evento(etapa, status, t0, {"fingerprint": fp[:16], **contagens(resultado)})
        return resultado


def _n_exc(s: Saida) -> dict:
    return {"excecoes": len(s.resultado.excecoes), "rastro": len(s.rastro.linhas())}


def fechar(mes: str, dados: Path, saida: Path, estado: Path | None = None,
           cliente: ClienteLLM | None | str = "padrao", cache: Path | None = None) -> ResultadoFechamento:
    dados, saida = Path(dados), Path(saida)
    db = Estado(estado) if estado is not None else None
    execucao_id = db.iniciar_execucao(mes) if db else None
    try:
        res = _fechar(mes, dados, saida, db, execucao_id, Checkpoints(estado, mes),
                      cliente_padrao() if cliente == "padrao" else cliente, cache or pasta_cache())
        if db:
            db.terminar_execucao(execucao_id, "CONCLUIDA")
        return res
    except Exception as exc:
        if db:
            db.terminar_execucao(execucao_id, "ERRO", f"{type(exc).__name__}: {exc}")
        raise
    finally:
        if db:
            db.fechar()


def _fechar(mes, dados, saida, db, execucao_id, ck, cliente, cache) -> ResultadoFechamento:
    arqs = {k: _arquivos(dados, p) for k, p in ARQUIVOS.items()}
    promovidas = db.regras() if db else []
    decisoes = db.decisoes(mes) if db else []
    bruto = mesclar_promovidas(ler_yaml(), promovidas)
    cfg = construir_config(bruto)
    ex = _Executor(ck, db, execucao_id)

    # Fingerprints: código + entradas + o trecho de configuração e as decisões que cada etapa usa.
    codigo = hash_codigo()
    cadastro = {k: bruto.get(k) for k in ("ecs_extra", "sem_contrato", "aliases", "overrides_taxa")}
    decisoes_conta = {d["payload"]["ref_origem"]: d["payload"]["conta"] for d in decisoes if d["tipo_decisao"] == "CONTA"}
    fp_ing = fingerprint("ingestao", codigo, {k: [(p.name, hash_arquivo(p)) for p in v] for k, v in arqs.items()})
    fp_chk = fingerprint("checkout", codigo, fp_ing, cadastro, mes)
    fp_div = fingerprint("divergencias", codigo, fp_chk, mes)
    fp_rem = fingerprint("remessa", codigo, fp_ing, cadastro, mes)
    fp_not = fingerprint("notas", codigo, fp_chk, fp_rem, mes)
    fp_ban = fingerprint("bancos", codigo, fp_ing, decisoes_conta, mes,
                         {k: bruto.get(k) for k in ("regras_lancamento", "conta_provisoria", "alertas_lancamento")})

    ing: Ingestao = ex.rodar("ingestao", fp_ing, lambda: _ingerir(arqs),
                             lambda i: {"orbe": len(i.txs), "ponte": len(i.ops), "taxas": len(i.contratos),
                                        "aurora": len(i.aurora.lancamentos), "meridiano": len(i.meridiano.lancamentos)})
    txs_mes = [t for t in ing.txs if no_mes(t.data_movimento, mes)]
    ops_mes = [o for o in ing.ops if no_mes(o.data_contratacao, mes)]
    avisos = checar_mes_com_dados(len(txs_mes), len(ops_mes), mes)

    chk: Saida = ex.rodar("checkout", fp_chk, lambda: _checkout(ing, cfg, mes), _n_exc)
    div: Saida = ex.rodar("divergencias", fp_div, lambda: _divergencias(chk, mes), _n_exc)
    rem: Saida = ex.rodar("remessa", fp_rem, lambda: _remessa(ing, cfg, mes), _n_exc)
    nts: Saida = ex.rodar("notas", fp_not, lambda: _notas(chk, rem, mes), _n_exc)
    ban: Saida = ex.rodar("bancos", fp_ban, lambda: _bancos(ing, cfg, mes, decisoes_conta), _n_exc)

    # --- agentes: o orquestrador só atua no que os motores não souberam resolver -------------------------
    t0 = time.perf_counter()
    excecoes = (ing.excecoes_taxas + ing.excecoes_orbe + chk.resultado.excecoes + div.resultado.excecoes + rem.resultado.excecoes
                + nts.resultado.excecoes + ban.resultado.excecoes)
    rastro_todo = ing.rastro.linhas() + chk.rastro.linhas() + div.rastro.linhas() + rem.rastro.linhas() \
        + nts.rastro.linhas() + ban.rastro.linhas()
    por_id: dict[str, list[LinhaRastro]] = collections.defaultdict(list)
    for l in rastro_todo:
        por_id[l.id_saida].append(l)
    ctx = Contexto(ing.plano, ing.aurora.lancamentos + ing.meridiano.lancamentos, ing.txs, ing.contratos, por_id)
    ag = orquestrar(excecoes, ban.resultado.lancamentos, ctx, cfg, cliente, {d["id_saida"] for d in decisoes}, cache)
    origens = collections.Counter(c.origem for c in ag.chamadas)
    ex.evento("agentes", "executada", t0, {"roteadas": len(ag.chamadas), **origens,
                                           "aplicadas": sum(c.resultado == "APLICADA" for c in ag.chamadas)})
    if db:
        for c in ag.chamadas:
            db.registrar_chamada(execucao_id, c.agente, c.id_saida, c.hash, c.origem, c.resultado, c.detalhe)

    # --- consolidação ----------------------------------------------------------------------------------
    t0 = time.perf_counter()
    resolvidas = {e.id_saida for e in excecoes} - {e.id_saida for e in ag.excecoes}
    rastro = Rastro()
    for l in rastro_todo:
        if l.id_saida in resolvidas:
            continue
        rastro.add(l.id_saida, l.arquivo_origem, l.ref_origem, l.valor, l.componente, l.taxa_usada_pct,
                   ag.regra_lancamento.get(l.id_saida, l.regra_id))
    notas_por_decisao = {d["id_saida"]: f"{d['decidido_por']}: {d['payload'].get('texto') or d['motivo']}"
                         for d in decisoes}
    # quem_decide e bloqueante vêm da configuração (P7); o default do código só vale para tipo não configurado.
    pendencias = [
        {"id_saida": e.id_saida, "tipo": e.tipo.value, "ref_origem": e.ref_origem,
         "valor_brl": e.valor_brl, "motivo": e.motivo, "quem_decide": cfg.quem_decide.get(e.tipo, e.quem_decide),
         "bloqueante": "S" if e.tipo in cfg.bloqueantes else "N",
         **{c: "" for c in COLUNAS_IA}, **ag.enriquecimento.get(e.id_saida, {}),
         **({"decisao": notas_por_decisao[e.id_saida]} if e.id_saida in notas_por_decisao else {})}
        for e in ag.excecoes
    ]
    comissoes = chk.resultado.comissoes + rem.resultado.comissoes
    divergencias = div.resultado.divergencias + rem.resultado.divergencias
    notas = nts.resultado.notas
    lancamentos = ag.lancamentos
    ledger = Ledger()
    for l in (ing.ledger, chk.ledger, rem.ledger, ban.ledger):
        ledger.juntar(l)

    # Valida antes de escrever: falha de invariante não deixa saída parcial.
    validar_i_r1({"comissoes_por_lojista": comissoes, "divergencias_taxa": divergencias,
                  "notas_a_emitir": notas, "lancamentos_classificados": lancamentos,
                  "pendencias": pendencias}, rastro)
    aurora, meridiano = ing.aurora, ing.meridiano
    bancos_mes: dict[str, set[str]] = {}
    for l in aurora.lancamentos + meridiano.lancamentos:
        if no_mes(l.data, mes):
            bancos_mes.setdefault(l.arquivo, set()).add(l.ref_origem)
    orbe_mes: dict[str, set[str]] = {}
    for t in txs_mes:
        orbe_mes.setdefault(t.arquivo, set()).add(t.id_transacao)
    ponte_mes: dict[str, set[str]] = {}  # operação repetida entre arquivos: o rastro aponta para o primeiro
    for o in sorted(ops_mes, key=lambda o: (o.arquivo, o.linha_fisica)):
        if not any(o.n_operacao in ids for ids in ponte_mes.values()):
            ponte_mes.setdefault(o.arquivo, set()).add(o.n_operacao)
    validar_i_r3({**orbe_mes, **ponte_mes, **bancos_mes}, rastro)
    validar_i_d1(divergencias)
    validar_i_n1(notas)
    validar_i_c1(lancamentos, ing.plano)
    orbe_todas: dict[str, set[str]] = {}
    for t in ing.txs + [s.descartada for s in ing.trocas_orbe]:
        orbe_todas.setdefault(t.arquivo, set()).add(t.id_transacao)
    ponte_todas: dict[str, set[str]] = {}
    for o in ing.ops:
        ponte_todas.setdefault(o.arquivo, set()).add(o.n_operacao)
    validar_i_r2({**orbe_todas, **ponte_todas, **ing.refs_taxas,
                  **{arq: {l.ref_origem for l in e.lancamentos}
                     for e in (aurora, meridiano) for arq in {l.arquivo for l in e.lancamentos}}}, rastro)
    validacoes = "I-R1, I-R2, I-R3, I-D1, I-N1, I-C1 ok"

    saida.mkdir(parents=True, exist_ok=True)
    escrever_csv(saida / "comissoes_por_lojista.csv", "comissoes_por_lojista", comissoes)
    escrever_csv(saida / "divergencias_taxa.csv", "divergencias_taxa", divergencias)
    escrever_csv(saida / "notas_a_emitir.csv", "notas_a_emitir", notas)
    escrever_csv(saida / "lancamentos_classificados.csv", "lancamentos_classificados", lancamentos)
    escrever_csv(saida / "pendencias.csv", "pendencias", pendencias)
    escrever_rastro(saida / "rastro.csv", rastro)
    (saida / "resumo.md").write_text(
        gerar_resumo(mes, comissoes, divergencias, notas, lancamentos, pendencias, ing.plano, validacoes),
        encoding="utf-8")

    banres = ban.resultado
    por_metodo = collections.Counter(l["metodo"] for l in lancamentos)
    # Sem carimbo de data nem origem (cache/API) das respostas: o log é idêntico entre execuções.
    linhas_log = [
        f"fechamento {mes}",
        f"arquivos: {', '.join(ing.nomes[k] for k in ('orbe', 'taxas', 'ponte', 'plano', 'aurora', 'meridiano'))}",
        f"Orbe: {len(ing.txs)} linha(s), {len(txs_mes)} no mês, {len(ing.txs) - len(txs_mes)} fora do mês",
        f"Ponte: {len(ing.ops)} linha(s), {len(ops_mes)} no mês, {len(ing.ops) - len(ops_mes)} fora do mês",
        *([f"Orbe: {ing.n_arquivos['orbe']} arquivo(s) somados ({ing.nomes['orbe']}); "
           f"{len(ing.trocas_orbe)} linha(s) com id repetido (a mais recente permanece, a mais antiga sai)"]
          if ing.n_arquivos["orbe"] > 1 else []),
        *[f"{rotulo}: {ing.n_arquivos[k]} arquivos somados ({ing.nomes[k]})"
          for k, rotulo in (("taxas", "Taxas"), ("ponte", "Ponte"), ("plano", "Plano de contas"),
                            ("aurora", "Aurora"), ("meridiano", "Meridiano")) if ing.n_arquivos[k] > 1],
        f"Taxas: {len(ing.contratos)} linha(s) de contrato",
        f"Plano de contas: {len(ing.plano)} conta(s), {sum(c.analitica for c in ing.plano.values())} analítica(s)",
        f"Aurora: {len(aurora.lancamentos)} lançamento(s); cadeia de saldos conferida dentro de cada um dos "
        f"{ing.n_arquivos['aurora']} arquivos" if ing.n_arquivos["aurora"] > 1
        else f"Aurora: {len(aurora.lancamentos)} lançamento(s); cadeia de saldos fecha "
        f"(R$ {fmt(aurora.saldo_inicial)} -> R$ {fmt(aurora.saldo_final)})" if aurora.saldo_inicial is not None
        else f"Aurora: {len(aurora.lancamentos)} lançamento(s); sem SALDO ANTERIOR, cadeia conferida a partir da 1ª linha",
        f"Meridiano: {len(meridiano.lancamentos)} lançamento(s); OFX sem saldo inicial, cadeia não verificável",
        f"Meridiano: {banres.conciliadas} TED(s) à Ponte conciliada(s) com Σ(Valor R$ + IOF) das operações do dia",
        f"Meridiano: PIX recebidos de lojistas − TEDs à Ponte no mês = R$ {fmt(banres.saldo_recursos_remessa)} "
        f"(recursos para remessas ainda não liquidados)",
        *ledger.linhas_log(),
        *[f"AVISO: {a}" for a in avisos],
        f"agentes: {len(ag.chamadas)} exceção(ões) roteada(s), "
        f"{sum(c.origem in ('cache', 'api') for c in ag.chamadas)} com resposta, "
        f"{sum(c.resultado == 'APLICADA' for c in ag.chamadas)} aplicada(s)",
        f"decisões humanas aplicadas: {len(decisoes)}; regras promovidas ativas: {len(promovidas)}",
        f"validação: {validacoes}",
        f"comissoes_por_lojista: {len(comissoes)} linha(s)",
        f"divergencias_taxa: {len(divergencias)} linha(s)",
        f"notas_a_emitir: {len(notas)} linha(s)",
        f"lancamentos_classificados: {len(lancamentos)} linha(s), "
        + ", ".join(f"{n} por {m}" for m, n in sorted(por_metodo.items())),
        f"pendencias: {len(pendencias)} linha(s), {sum(p['bloqueante'] == 'S' for p in pendencias)} bloqueante(s)",
        *[f"  {t}: {n}" for t, n in sorted(collections.Counter(p["tipo"] for p in pendencias).items())],
        f"rastro: {len(rastro.linhas())} linha(s)",
    ]
    (saida / "execucao.log").write_text("\n".join(linhas_log) + "\n", encoding="utf-8")
    if db:
        db.atualizar_fila(mes, pendencias)
    ex.evento("consolidacao", "executada", t0, {"pendencias": len(pendencias), "rastro": len(rastro.linhas())})
    return ResultadoFechamento(comissoes, divergencias, ag.excecoes, notas, lancamentos, ex.etapas, ag, execucao_id)
