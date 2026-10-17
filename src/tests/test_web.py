import csv
import hashlib
import json
import threading
from decimal import Decimal
from http.server import ThreadingHTTPServer
from shutil import copyfile
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

import pytest
import tarvo.web as web
from tarvo.pipeline import fechar
from tarvo.web import _SLOTS, _format_brl, _original_row, _summary


def test_web_summary_matches_real_pipeline_outputs(dados, tmp_path):
    output = tmp_path / "saida"
    fechar("2026-09", dados, output)

    summary = _summary(output)

    assert summary["checkout"] == "R$ 203.735,34"
    assert summary["remessa"] == "R$ 39.543,45"
    assert summary["divergences_count"] == 233
    assert summary["notes_count"] == 21
    assert summary["bank_entries_count"] == 184
    assert summary["pending_count"] == 18
    assert summary["pending_by_decider"] == {"Helena e Diego": 2, "Helena": 15, "Diego": 1}
    assert summary["reconciles"] is True


def test_brl_format_uses_brazilian_separators():
    assert _format_brl(Decimal("-1234567.89")) == "R$ -1.234.567,89"


def test_detail_lookup_returns_original_rows_for_pipeline_sources(dados, tmp_path):
    closure_dir = tmp_path / "closure"
    input_dir = closure_dir / "dados"
    input_dir.mkdir(parents=True)
    source_files = {
        "orbe": ("01_*.csv", "AN88445172"),
        "ponte": ("03_*.eml", "PC-0926-0023"),
        "aurora": ("05a_*.csv", "L10"),
        "meridiano": ("05b_*.ofx", "MRD2026090003"),
        "ajustes": ("06_*.csv", "TX88447225"),  # linha vinda do 06, outro arquivo do mesmo campo da Orbe
    }
    for pattern, _ in source_files.values():
        source = next(dados.glob(pattern))
        copyfile(source, input_dir / source.name)

    for pattern, reference in source_files.values():
        row = _original_row(closure_dir, next(dados.glob(pattern)).name, reference)
        assert row is not None
        assert reference in row.values()


@pytest.fixture
def web_server(monkeypatch, tmp_path):
    monkeypatch.setenv("TARVO_SEM_IA", "1")
    monkeypatch.setattr(web, "_DATA_ROOT", tmp_path / "web-data")
    server = ThreadingHTTPServer(("127.0.0.1", 0), web._Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _http_json(url, payload=None, method=None, timeout=90):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=data,
        method=method or ("POST" if data is not None else "GET"),
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def test_web_end_to_end_events_decisions_and_close_gate(dados, web_server):
    status, closure = _http_json(f"{web_server}/api/closures", {"month": "2026-09"})
    assert status == 201
    closure_id = closure["id"]
    source_files = {
        "orbe": "01_*.csv",
        "taxas": "02_*.xlsx",
        "ponte": "03_*.eml",
        "plano": "04_*.csv",
        "aurora": "05a_*.csv",
        "meridiano": "05b_*.ofx",
    }
    for slot, pattern in source_files.items():
        source = next(dados.glob(pattern))
        request = Request(
            f"{web_server}/api/closures/{closure_id}/files/{slot}",
            data=source.read_bytes(),
            method="POST",
            headers={"X-Filename": quote(source.name), "Content-Type": "application/octet-stream"},
        )
        with urlopen(request, timeout=10) as response:
            assert response.status == 200

    status, validation = _http_json(f"{web_server}/api/closures/{closure_id}/validate", method="POST")
    assert status == 200 and validation["status"] == "validated"
    assert validation["summary"]["reconciles"] is True

    status, running = _http_json(f"{web_server}/api/closures/{closure_id}/run", method="POST")
    assert status == 202 and running["status"] == "running"
    with urlopen(f"{web_server}/api/closures/{closure_id}/events", timeout=90) as response:
        events_stream = response.read().decode("utf-8")
    assert "event: progress" in events_stream and "event: complete" in events_stream

    status, activity = _http_json(f"{web_server}/api/closures/{closure_id}/activity")
    assert status == 200 and activity["execution"]["status"] == "CONCLUIDA"
    assert [event["etapa"] for event in activity["events"]][-2:] == ["agentes", "consolidacao"]
    status, queue = _http_json(f"{web_server}/api/closures/{closure_id}/queue")
    assert status == 200 and queue["open_count"] == 18 and queue["blocking_count"] == 0

    status, decision = _http_json(
        f"{web_server}/api/closures/{closure_id}/decisions",
        {
            "id_saida": "PEN-DIVERGENCIA_ORBE-22224579000109-202609",
            "tipo_decisao": "NOTA",
            "escopo": "caso",
            "texto": "Cobrar a diferença na conciliação seguinte.",
            "autor": "Analista",
            "motivo": "Divergência confirmada com a adquirente.",
        },
    )
    assert status == 202 and decision["status"] == "running"
    with urlopen(f"{web_server}/api/closures/{closure_id}/events", timeout=90) as response:
        rerun_stream = response.read().decode("utf-8")
    assert "event: complete" in rerun_stream
    status, activity = _http_json(f"{web_server}/api/closures/{closure_id}/activity")
    assert status == 200 and activity["execution"]["status"] == "CONCLUIDA"

    closure_dir = web._DATA_ROOT / "fechamentos" / closure_id
    pending_path = closure_dir / "saida" / "pendencias.csv"
    original_pending = pending_path.read_bytes()
    with pending_path.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source, delimiter=";"))
        fields = rows[0].keys()
    rows[0]["bloqueante"] = "S"
    with pending_path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields, delimiter=";", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    status, blocked = _http_json(
        f"{web_server}/api/closures/{closure_id}/close",
        {"autor": "Analista", "motivo": "Revisão final."},
    )
    assert status == 409 and blocked["blocking_count"] == 1
    pending_path.write_bytes(original_pending)

    status, closed = _http_json(
        f"{web_server}/api/closures/{closure_id}/close",
        {"autor": "Analista", "motivo": "Revisão final concluída."},
    )
    assert status == 200 and closed["status"] == "closed" and closed["closed"] is True
    assert closed["closure_record"]["files_sha256"]["pendencias.csv"] == hashlib.sha256(original_pending).hexdigest()
    status, table = _http_json(f"{web_server}/api/closures/{closure_id}/tables/pendencias")
    assert status == 200 and len(table["rows"]) == 18


def test_web_campo_aceita_varios_arquivos_e_o_orbe_junta_relatorio_e_ajustes(dados, web_server):
    status, closure = _http_json(f"{web_server}/api/closures", {"month": "2026-09"})
    closure_id = closure["id"]
    url = f"{web_server}/api/closures/{closure_id}/files"

    def enviar(slot, source, metodo="POST"):
        request = Request(f"{url}/{slot}", data=source.read_bytes(), method=metodo,
                          headers={"X-Filename": quote(source.name), "Content-Type": "application/octet-stream"})
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read())

    for slot, pattern in {"orbe": "01_*.csv", "taxas": "02_*.xlsx", "ponte": "03_*.eml", "plano": "04_*.csv",
                          "aurora": "05a_*.csv", "meridiano": "05b_*.ofx"}.items():
        enviar(slot, next(dados.glob(pattern)))
    estado = enviar("orbe", next(dados.glob("06_*.csv")))  # o 06 vai no mesmo campo do 01
    assert [n[:3] for n in estado["files"]["orbe"]] == ["01_", "06_"]

    status, validation = _http_json(f"{web_server}/api/closures/{closure_id}/validate", method="POST")
    assert status == 200 and validation["summary"]["checkout"] == "R$ 203.735,34"


def test_web_limpar_campo_remove_os_arquivos_e_bloqueia_a_validacao(dados, web_server):
    status, closure = _http_json(f"{web_server}/api/closures", {"month": "2026-09"})
    url = f"{web_server}/api/closures/{closure['id']}/files/orbe"
    source = next(dados.glob("01_*.csv"))
    request = Request(url, data=source.read_bytes(), method="POST",
                      headers={"X-Filename": quote(source.name), "Content-Type": "application/octet-stream"})
    with urlopen(request, timeout=10):
        pass
    status, estado = _http_json(url, method="DELETE")
    assert status == 200 and "orbe" not in estado["files"]
    status, erro = _http_json(f"{web_server}/api/closures/{closure['id']}/validate", method="POST")
    assert status == 409 and "Orbe" in erro["error"]
