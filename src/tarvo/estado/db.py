"""Estado do fechamento em SQLite (PRD 3, 8.4): execuções, eventos por etapa, fila de exceções, decisões
humanas, regras promovidas e chamadas de agentes. Um arquivo só, sem servidor. Fica fora do git (data/).

As saídas de saida/ nunca leem data/hora daqui: o carimbo de tempo só existe no estado, para auditoria."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS execucoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, mes TEXT NOT NULL, iniciada_em TEXT NOT NULL,
    terminada_em TEXT, status TEXT NOT NULL, erro TEXT);
CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT, execucao_id INTEGER NOT NULL, ordem INTEGER NOT NULL,
    etapa TEXT NOT NULL, status TEXT NOT NULL, duracao_ms INTEGER, detalhe TEXT, criado_em TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS fila (
    mes TEXT NOT NULL, id_saida TEXT NOT NULL, tipo TEXT NOT NULL, ref_origem TEXT NOT NULL,
    valor_brl TEXT NOT NULL, motivo TEXT NOT NULL, quem_decide TEXT NOT NULL, bloqueante TEXT NOT NULL,
    estado TEXT NOT NULL, proposta TEXT, atualizado_em TEXT NOT NULL, PRIMARY KEY (mes, id_saida));
CREATE TABLE IF NOT EXISTS decisoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, mes TEXT NOT NULL, id_saida TEXT NOT NULL, tipo_decisao TEXT NOT NULL,
    payload TEXT NOT NULL, escopo TEXT NOT NULL, decidido_por TEXT NOT NULL, motivo TEXT NOT NULL,
    decidido_em TEXT NOT NULL, ativa INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS regras (
    id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL, payload TEXT NOT NULL, autor TEXT NOT NULL,
    motivo TEXT NOT NULL, criada_em TEXT NOT NULL, ativa INTEGER NOT NULL DEFAULT 1, decisao_id INTEGER);
CREATE TABLE IF NOT EXISTS agentes_chamadas (
    id INTEGER PRIMARY KEY AUTOINCREMENT, execucao_id INTEGER NOT NULL, agente TEXT NOT NULL,
    id_saida TEXT NOT NULL, hash TEXT NOT NULL, origem TEXT NOT NULL, resultado TEXT NOT NULL, detalhe TEXT);
"""

# Estados de um item da fila (PRD 8.5).
AGUARDANDO = "AGUARDANDO_HUMANO"
AGENTE_PROPOS = "AGENTE_PROPOS"
DECIDIDA = "DECIDIDA"
RESOLVIDA = "RESOLVIDA"  # saiu das pendências (regra, decisão de conta ou agente acima do limiar)

TIPOS_DECISAO = {"CONTA", "NOTA", "EC_LOJISTA"}
ESCOPOS = {"caso", "regra"}


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _json(v) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, default=str)


class Estado:
    def __init__(self, pasta: Path):
        self.pasta = Path(pasta)
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.pasta / "tarvo.db")
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)

    def fechar(self) -> None:
        self.con.close()

    # --- execuções e eventos ---------------------------------------------------------------------------
    def iniciar_execucao(self, mes: str) -> int:
        cur = self.con.execute("INSERT INTO execucoes (mes, iniciada_em, status) VALUES (?, ?, 'EXECUTANDO')",
                               (mes, _agora()))
        self.con.commit()
        return cur.lastrowid

    def terminar_execucao(self, execucao_id: int, status: str, erro: str | None = None) -> None:
        self.con.execute("UPDATE execucoes SET terminada_em = ?, status = ?, erro = ? WHERE id = ?",
                         (_agora(), status, erro, execucao_id))
        self.con.commit()

    def evento(self, execucao_id: int, ordem: int, etapa: str, status: str, duracao_ms: int | None,
               detalhe: dict | None = None) -> None:
        self.con.execute("INSERT INTO eventos (execucao_id, ordem, etapa, status, duracao_ms, detalhe, criado_em) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (execucao_id, ordem, etapa, status, duracao_ms, _json(detalhe or {}), _agora()))
        self.con.commit()

    def eventos(self, execucao_id: int) -> list[dict]:
        rows = self.con.execute("SELECT * FROM eventos WHERE execucao_id = ? ORDER BY ordem", (execucao_id,))
        return [{**dict(r), "detalhe": json.loads(r["detalhe"])} for r in rows]

    def ultima_execucao(self, mes: str) -> dict | None:
        r = self.con.execute("SELECT * FROM execucoes WHERE mes = ? ORDER BY id DESC LIMIT 1", (mes,)).fetchone()
        return dict(r) if r else None

    # --- fila --------------------------------------------------------------------------------------------
    def atualizar_fila(self, mes: str, pendencias: list[dict]) -> None:
        """Pendência presente entra ou é atualizada; a que não aparece mais é marcada RESOLVIDA."""
        decididas = {d["id_saida"] for d in self.decisoes(mes)}
        atuais = set()
        for p in pendencias:
            atuais.add(p["id_saida"])
            proposta = p.get("proposta_ia") or p.get("hipoteses_ia") or ""
            estado = DECIDIDA if p["id_saida"] in decididas else (AGENTE_PROPOS if proposta else AGUARDANDO)
            self.con.execute(
                "INSERT INTO fila (mes, id_saida, tipo, ref_origem, valor_brl, motivo, quem_decide, bloqueante, "
                "estado, proposta, atualizado_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (mes, id_saida) DO UPDATE SET tipo = excluded.tipo, ref_origem = excluded.ref_origem, "
                "valor_brl = excluded.valor_brl, motivo = excluded.motivo, quem_decide = excluded.quem_decide, "
                "bloqueante = excluded.bloqueante, estado = excluded.estado, proposta = excluded.proposta, "
                "atualizado_em = excluded.atualizado_em",
                (mes, p["id_saida"], p["tipo"], p["ref_origem"], str(p["valor_brl"]), p["motivo"], p["quem_decide"],
                 p["bloqueante"], estado, proposta, _agora()))
        for r in self.con.execute("SELECT id_saida FROM fila WHERE mes = ? AND estado != ?", (mes, RESOLVIDA)).fetchall():
            if r["id_saida"] not in atuais:
                self.con.execute("UPDATE fila SET estado = ?, atualizado_em = ? WHERE mes = ? AND id_saida = ?",
                                 (RESOLVIDA, _agora(), mes, r["id_saida"]))
        self.con.commit()

    def fila(self, mes: str, incluir_resolvidas: bool = False) -> list[dict]:
        sql = "SELECT * FROM fila WHERE mes = ?" + ("" if incluir_resolvidas else " AND estado != 'RESOLVIDA'")
        return [dict(r) for r in self.con.execute(sql + " ORDER BY bloqueante DESC, quem_decide, id_saida", (mes,))]

    def item_fila(self, mes: str, id_saida: str) -> dict | None:
        r = self.con.execute("SELECT * FROM fila WHERE mes = ? AND id_saida = ?", (mes, id_saida)).fetchone()
        return dict(r) if r else None

    # --- decisões e regras -------------------------------------------------------------------------------
    def registrar_decisao(self, mes: str, id_saida: str, tipo_decisao: str, payload: dict, escopo: str,
                          decidido_por: str, motivo: str) -> int:
        if tipo_decisao not in TIPOS_DECISAO or escopo not in ESCOPOS:
            raise ValueError(f"decisão inválida: {tipo_decisao}/{escopo}")
        if not decidido_por.strip() or not motivo.strip():
            raise ValueError("decisão precisa de autor e motivo (P12)")
        # Uma decisão ativa por item: a nova substitui a anterior, que fica no histórico.
        self.con.execute("UPDATE decisoes SET ativa = 0 WHERE mes = ? AND id_saida = ?", (mes, id_saida))
        cur = self.con.execute(
            "INSERT INTO decisoes (mes, id_saida, tipo_decisao, payload, escopo, decidido_por, motivo, decidido_em) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (mes, id_saida, tipo_decisao, _json(payload), escopo, decidido_por, motivo, _agora()))
        self.con.commit()
        return cur.lastrowid

    def decisoes(self, mes: str) -> list[dict]:
        rows = self.con.execute("SELECT * FROM decisoes WHERE mes = ? AND ativa = 1 ORDER BY id", (mes,))
        return [{**dict(r), "payload": json.loads(r["payload"])} for r in rows]

    def historico_decisoes(self, mes: str) -> list[dict]:
        """Todas as decisões do mês, ativas ou substituídas, em ordem de registro."""
        rows = self.con.execute("SELECT * FROM decisoes WHERE mes = ? ORDER BY id", (mes,))
        return [{**dict(r), "payload": json.loads(r["payload"])} for r in rows]

    def promover_regra(self, tipo: str, payload: dict, autor: str, motivo: str, decisao_id: int | None) -> int:
        cur = self.con.execute(
            "INSERT INTO regras (tipo, payload, autor, motivo, criada_em, decisao_id) VALUES (?, ?, ?, ?, ?, ?)",
            (tipo, _json(payload), autor, motivo, _agora(), decisao_id))
        self.con.commit()
        return cur.lastrowid

    def regras(self, so_ativas: bool = True) -> list[dict]:
        sql = "SELECT * FROM regras" + (" WHERE ativa = 1" if so_ativas else "") + " ORDER BY id"
        return [{**dict(r), "payload": json.loads(r["payload"])} for r in self.con.execute(sql)]

    def desativar_regra(self, regra_id: int) -> None:
        self.con.execute("UPDATE regras SET ativa = 0 WHERE id = ?", (regra_id,))
        self.con.commit()

    # --- agentes -----------------------------------------------------------------------------------------
    def registrar_chamada(self, execucao_id: int, agente: str, id_saida: str, hash_: str, origem: str,
                          resultado: str, detalhe: str = "") -> None:
        self.con.execute("INSERT INTO agentes_chamadas (execucao_id, agente, id_saida, hash, origem, resultado, detalhe) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?)", (execucao_id, agente, id_saida, hash_, origem, resultado, detalhe))
        self.con.commit()

    def chamadas(self, execucao_id: int) -> list[dict]:
        rows = self.con.execute(
            "SELECT agente, id_saida, origem, resultado, detalhe FROM agentes_chamadas "
            "WHERE execucao_id = ? ORDER BY id",
            (execucao_id,),
        )
        return [dict(row) for row in rows]
