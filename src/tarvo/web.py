"""Interface web local para executar o motor e consultar as saídas reais."""
from __future__ import annotations

import csv
import json
import re
import uuid
import zipfile
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from .ingest.erros import LayoutError
from .output.validators import ValidationError
from .pipeline import fechar

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_WEB_ROOT = Path(__file__).resolve().parent / "web"
_DATA_ROOT = _PROJECT_ROOT / "data" / "web"
_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_SLOTS = {
    "orbe": (".csv", "01_upload.csv"),
    "taxas": (".xlsx", "02_upload.xlsx"),
    "ponte": (".eml", "03_upload.eml"),
}
_TABLES = {
    "comissoes": "comissoes_por_lojista.csv",
    "divergencias": "divergencias_taxa.csv",
    "notas": "notas_a_emitir.csv",
    "pendencias": "pendencias.csv",
    "rastro": "rastro.csv",
}
_DOWNLOADS = (*_TABLES.values(), "execucao.log")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source, delimiter=";"))


def _format_brl(value: Decimal) -> str:
    return f"R$ {value:,.2f}".replace(",", "\0").replace(".", ",").replace("\0", ".")


def _summary(output_dir: Path) -> dict:
    commissions = _read_csv(output_dir / _TABLES["comissoes"])
    divergences = _read_csv(output_dir / _TABLES["divergencias"])
    notes = _read_csv(output_dir / _TABLES["notas"])
    pending = _read_csv(output_dir / _TABLES["pendencias"])
    trace = _read_csv(output_dir / _TABLES["rastro"])

    totals = {
        line: sum(
            (Decimal(row["comissao_brl"]) for row in commissions if row["linha_negocio"] == line),
            Decimal("0"),
        )
        for line in ("CHECKOUT", "REMESSA")
    }
    trace_totals: dict[str, Decimal] = {}
    for row in trace:
        key = row["id_saida"]
        trace_totals[key] = trace_totals.get(key, Decimal("0")) + Decimal(row["valor"])

    reconciles = all(
        trace_totals.get(row["id_saida"], Decimal("0")) == Decimal(row[value_column])
        for rows, value_column in (
            (commissions, "comissao_brl"),
            (divergences, "diferenca_brl"),
            (notes, "valor_brl"),
            (pending, "valor_brl"),
        )
        for row in rows
    )
    by_decider: dict[str, int] = {}
    for row in pending:
        decider = row.get("quem_decide") or "Não definido"
        by_decider[decider] = by_decider.get(decider, 0) + 1

    return {
        "checkout": _format_brl(totals["CHECKOUT"]),
        "remessa": _format_brl(totals["REMESSA"]),
        "divergences_count": len(divergences),
        "divergences_total": _format_brl(
            sum((Decimal(row["diferenca_brl"]) for row in divergences), Decimal("0"))
        ),
        "notes_count": len(notes),
        "notes_total": _format_brl(
            sum((Decimal(row["valor_brl"]) for row in notes), Decimal("0"))
        ),
        "pending_count": len(pending),
        "pending_by_decider": by_decider,
        "reconciles": reconciles,
    }


def _load_state(closure_id: str) -> tuple[Path, dict]:
    try:
        normalized_id = str(uuid.UUID(closure_id))
    except ValueError as exc:
        raise FileNotFoundError("Fechamento não encontrado.") from exc
    closure_dir = _DATA_ROOT / "fechamentos" / normalized_id
    state_path = closure_dir / "state.json"
    if not state_path.is_file():
        raise FileNotFoundError("Fechamento não encontrado.")
    with state_path.open(encoding="utf-8") as source:
        return closure_dir, json.load(source)


def _save_state(closure_dir: Path, state: dict) -> None:
    with (closure_dir / "state.json").open("w", encoding="utf-8") as target:
        json.dump(state, target, ensure_ascii=False, indent=2)


def _response_state(closure_dir: Path, state: dict) -> dict:
    response = {
        "id": state["id"],
        "month": state["month"],
        "status": state["status"],
        "files": state["files"],
        "validation_error": state.get("validation_error"),
    }
    result_dir = closure_dir / ("saida" if state["status"] == "completed" else "validacao")
    if state["status"] in {"validated", "completed"}:
        response["summary"] = _summary(result_dir)
        response["outputs"] = list(_TABLES)
    return response


class _Handler(BaseHTTPRequestHandler):
    server_version = "TarvoWeb/1.0"

    def do_GET(self) -> None:
        request = urlsplit(self.path)
        if request.path == "/":
            self._static("index.html", "text/html; charset=utf-8")
            return
        if request.path in {"/app.css", "/app.js"}:
            file_name = request.path.lstrip("/")
            content_type = "text/css; charset=utf-8" if file_name.endswith(".css") else "text/javascript; charset=utf-8"
            self._static(file_name, content_type)
            return
        match = re.fullmatch(r"/api/closures/([0-9a-f-]{36})", request.path)
        if match:
            self._get_closure(match.group(1))
            return
        match = re.fullmatch(r"/api/closures/([0-9a-f-]{36})/tables/(comissoes|divergencias|notas|pendencias|rastro)", request.path)
        if match:
            self._get_table(match.group(1), match.group(2))
            return
        match = re.fullmatch(r"/api/closures/([0-9a-f-]{36})/trace", request.path)
        if match:
            self._get_trace(match.group(1), parse_qs(request.query))
            return
        match = re.fullmatch(r"/api/closures/([0-9a-f-]{36})/download/([^/]+)", request.path)
        if match:
            self._download(match.group(1), match.group(2))
            return
        self._json({"error": "Endereço não encontrado."}, 404)

    def do_POST(self) -> None:
        request = urlsplit(self.path)
        if request.path == "/api/closures":
            self._create_closure()
            return
        match = re.fullmatch(r"/api/closures/([0-9a-f-]{36})/files/(orbe|taxas|ponte)", request.path)
        if match:
            self._upload_file(match.group(1), match.group(2))
            return
        match = re.fullmatch(r"/api/closures/([0-9a-f-]{36})/validate", request.path)
        if match:
            self._validate(match.group(1))
            return
        match = re.fullmatch(r"/api/closures/([0-9a-f-]{36})/run", request.path)
        if match:
            self._run(match.group(1))
            return
        self._json({"error": "Endereço não encontrado."}, 404)

    def log_message(self, format: str, *args) -> None:
        print(f"{self.log_date_time_string()} {self.address_string()} {format % args}")

    def _static(self, file_name: str, content_type: str) -> None:
        path = _WEB_ROOT / file_name
        if not path.is_file():
            self._json({"error": "Arquivo da interface não encontrado."}, 500)
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self';")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = self._content_length()
        if length > 64 * 1024:
            raise ValueError("A solicitação é maior do que o limite permitido.")
        try:
            payload = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as exc:
            raise ValueError("Envie os dados do formulário em JSON válido.") from exc
        if not isinstance(payload, dict):
            raise ValueError("Os dados enviados precisam ser um objeto.")
        return payload

    def _content_length(self) -> int:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise ValueError("A solicitação não informou o tamanho do arquivo.")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValueError("Tamanho de arquivo inválido.") from exc
        if length < 0:
            raise ValueError("Tamanho de arquivo inválido.")
        return length

    def _create_closure(self) -> None:
        try:
            payload = self._read_json()
        except ValueError as exc:
            self._json({"error": str(exc)}, 400)
            return
        month = payload.get("month")
        if not isinstance(month, str) or not _MONTH_RE.fullmatch(month):
            self._json({"error": "Informe o mês no formato AAAA-MM."}, 400)
            return
        closure_id = str(uuid.uuid4())
        closure_dir = _DATA_ROOT / "fechamentos" / closure_id
        (closure_dir / "dados").mkdir(parents=True, exist_ok=False)
        state = {"id": closure_id, "month": month, "status": "uploading", "files": {}}
        _save_state(closure_dir, state)
        self._json(_response_state(closure_dir, state), 201)

    def _upload_file(self, closure_id: str, slot: str) -> None:
        try:
            closure_dir, state = _load_state(closure_id)
        except FileNotFoundError as exc:
            self._json({"error": str(exc)}, 404)
            return
        if state["status"] != "uploading":
            self._json({"error": "Os arquivos só podem ser alterados antes da pré-validação."}, 409)
            return
        try:
            length = self._content_length()
        except ValueError as exc:
            self._json({"error": str(exc)}, 400)
            return
        if length == 0 or length > _MAX_UPLOAD_BYTES:
            self.close_connection = True
            self._json({"error": "O arquivo precisa ter conteúdo e não pode ultrapassar 25 MB."}, 413)
            return
        filename = unquote(self.headers.get("X-Filename", ""))
        expected_extension, stored_name = _SLOTS[slot]
        if not filename or Path(filename).name != filename or Path(filename).suffix.lower() != expected_extension:
            self._json({"error": f"Este campo aceita somente arquivos {expected_extension}."}, 415)
            return
        body = self.rfile.read(length)
        target = closure_dir / "dados" / stored_name
        target.write_bytes(body)
        state["files"][slot] = filename
        _save_state(closure_dir, state)
        self._json(_response_state(closure_dir, state))

    def _validate(self, closure_id: str) -> None:
        try:
            closure_dir, state = _load_state(closure_id)
        except FileNotFoundError as exc:
            self._json({"error": str(exc)}, 404)
            return
        missing = [slot for slot in _SLOTS if slot not in state["files"]]
        if missing:
            labels = {"orbe": "relatório Orbe", "taxas": "planilha de taxas", "ponte": "e-mail da Ponte"}
            self._json({"error": "Envie os arquivos obrigatórios: " + ", ".join(labels[slot] for slot in missing) + "."}, 409)
            return
        try:
            fechar(state["month"], closure_dir / "dados", closure_dir / "validacao")
        except (LayoutError, ValidationError, OSError, ValueError) as exc:
            state["validation_error"] = str(exc)
            state["status"] = "uploading"
            _save_state(closure_dir, state)
            self._json({"error": f"Não foi possível validar os arquivos: {exc}"}, 422)
            return
        state["status"] = "validated"
        state.pop("validation_error", None)
        _save_state(closure_dir, state)
        self._json(_response_state(closure_dir, state))

    def _run(self, closure_id: str) -> None:
        try:
            closure_dir, state = _load_state(closure_id)
        except FileNotFoundError as exc:
            self._json({"error": str(exc)}, 404)
            return
        if state["status"] != "validated":
            self._json({"error": "Pré-valide os arquivos antes de executar o fechamento."}, 409)
            return
        try:
            fechar(state["month"], closure_dir / "dados", closure_dir / "saida")
        except (LayoutError, ValidationError, OSError, ValueError) as exc:
            self._json({"error": f"Não foi possível concluir o fechamento: {exc}"}, 422)
            return
        state["status"] = "completed"
        _save_state(closure_dir, state)
        self._json(_response_state(closure_dir, state))

    def _get_closure(self, closure_id: str) -> None:
        try:
            closure_dir, state = _load_state(closure_id)
        except FileNotFoundError as exc:
            self._json({"error": str(exc)}, 404)
            return
        self._json(_response_state(closure_dir, state))

    def _get_table(self, closure_id: str, table: str) -> None:
        try:
            closure_dir, state = _load_state(closure_id)
        except FileNotFoundError as exc:
            self._json({"error": str(exc)}, 404)
            return
        if state["status"] != "completed":
            self._json({"error": "As saídas aparecem depois da execução do fechamento."}, 409)
            return
        try:
            rows = _read_csv(closure_dir / "saida" / _TABLES[table])
        except OSError as exc:
            self._json({"error": f"Não foi possível abrir a saída: {exc}"}, 500)
            return
        self._json({"rows": rows})

    def _get_trace(self, closure_id: str, query: dict[str, list[str]]) -> None:
        try:
            closure_dir, state = _load_state(closure_id)
        except FileNotFoundError as exc:
            self._json({"error": str(exc)}, 404)
            return
        if state["status"] != "completed":
            self._json({"error": "O rastro aparece depois da execução do fechamento."}, 409)
            return
        output_id = query.get("id_saida", [""])[0]
        if not output_id or len(output_id) > 128:
            self._json({"error": "Identificador de saída inválido."}, 400)
            return
        try:
            rows = _read_csv(closure_dir / "saida" / _TABLES["rastro"])
        except OSError as exc:
            self._json({"error": f"Não foi possível abrir o rastro: {exc}"}, 500)
            return
        self._json({"rows": [row for row in rows if row["id_saida"] == output_id]})

    def _download(self, closure_id: str, name: str) -> None:
        try:
            closure_dir, state = _load_state(closure_id)
        except FileNotFoundError as exc:
            self._json({"error": str(exc)}, 404)
            return
        if state["status"] != "completed":
            self._json({"error": "Os arquivos ficam disponíveis depois da execução."}, 409)
            return
        if name == "todos.zip":
            archive_path = closure_dir / "saida" / "todos.zip"
            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
                for file_name in _DOWNLOADS:
                    archive.write(closure_dir / "saida" / file_name, arcname=file_name)
            path = archive_path
            content_type = "application/zip"
        elif name in _DOWNLOADS:
            path = closure_dir / "saida" / name
            content_type = "text/plain; charset=utf-8" if name.endswith(".log") else "text/csv; charset=utf-8"
        else:
            self._json({"error": "Arquivo de saída não encontrado."}, 404)
            return
        try:
            body = path.read_bytes()
        except OSError as exc:
            self._json({"error": f"Não foi possível abrir a saída: {exc}"}, 500)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{name}"')
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)


def serve(port: int = 8000) -> None:
    if not 1 <= port <= 65535:
        raise ValueError("A porta precisa estar entre 1 e 65535.")
    _DATA_ROOT.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    print(f"Tarvo disponível em http://127.0.0.1:{port} (Ctrl+C para encerrar)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nInterface encerrada.")
    finally:
        server.server_close()
