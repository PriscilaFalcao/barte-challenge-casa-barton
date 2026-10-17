import io
from datetime import date, datetime
from decimal import Decimal as D
from email.message import EmailMessage

import openpyxl
import pytest

from tarvo.ingest.erros import LayoutError
from tarvo.ingest.ponte import ler_ponte

CAB = ["Nº Operação", "Data Contratação", "Data Liquidação", "CNPJ Cliente", "Cliente", "Moeda", "Valor ME",
       "Taxa Cliente", "PTAX Ref.", "Valor R$", "Spread R$", "Spread %", "Spread Estimado R$ (D-1)", "IOF R$",
       "Status Compliance", "Observação"]
OP = ["PC-0926-0002", datetime(2026, 9, 30), datetime(2026, 10, 1), "34.671.260/0001-00", "MAPLE STUDY", "NZD",
      5402.22, 3.2796, 3.2311, 17717.12, 262.01, 0.01501, 279.09, 67.33, "APROVADO", None]


def _xlsx(linhas, topo=4, sheet="Operações", cab=CAB, rodape=True):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet
    for i in range(topo):
        ws.append([f"titulo {i}"])
    ws.append(cab)
    for l in linhas:
        ws.append(l)
    if rodape:
        ws.append([None])
        ws.append(["Total de operações:", len(linhas)])
        ws.append(["Spread total R$:", 123.45])
    wb.create_sheet("Resumo").append(["Moeda", "Qtd", "Volume ME", "Spread R$"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _eml(tmp_path, anexos):
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = "r@ponte", "f@tarvo", "Relatório"
    m.set_content("corpo")
    for i, a in enumerate(anexos):
        m.add_attachment(a, maintype="application",
                         subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=f"r{i}.xlsx")
    p = tmp_path / "ponte.eml"
    p.write_bytes(m.as_bytes())
    return p


def test_parses_operation_fields(tmp_path):
    (op,) = ler_ponte(_eml(tmp_path, [_xlsx([OP])]))
    assert op.n_operacao == op.ref_origem == "PC-0926-0002"
    assert op.data_contratacao == date(2026, 9, 30) and op.data_liquidacao == date(2026, 10, 1)
    assert op.cnpj14 == "34671260000100"
    assert (op.valor_me, op.ptax, op.spread_brl) == (D("5402.22"), D("3.2311"), D("262.01"))
    assert op.spread_pct == D("0.01501")  # fração, como a Ponte reporta (1,501%)
    assert op.status == "APROVADO" and op.observacao is None
    assert op.linha_fisica == 6


def test_footer_total_rows_and_resumo_are_not_operations(tmp_path):
    ops = ler_ponte(_eml(tmp_path, [_xlsx([OP, [*OP[:0], "PC-0926-0003", *OP[1:]]])]))
    assert [o.n_operacao for o in ops] == ["PC-0926-0002", "PC-0926-0003"]


def test_header_found_by_text_regardless_of_row(tmp_path):
    a = ler_ponte(_eml(tmp_path, [_xlsx([OP], topo=4)]))
    b = ler_ponte(_eml(tmp_path, [_xlsx([OP], topo=9)]))
    assert (a[0].linha_fisica, b[0].linha_fisica) == (6, 11)


def test_duplicates_are_kept_in_file_order_for_the_engine_to_decide(tmp_path):
    dup = [*OP[:15], "reprocessada"]
    ops = ler_ponte(_eml(tmp_path, [_xlsx([OP, dup])]))
    assert [o.linha_fisica for o in ops] == [6, 7] and ops[1].observacao == "reprocessada"


def test_negative_spread_is_read_as_is(tmp_path):
    neg = [*OP[:10], -687.52, -0.015523, 587.97, 67.33, "APROVADO", "Taxa travada no pedido (D-1)"]
    (op,) = ler_ponte(_eml(tmp_path, [_xlsx([neg])]))
    assert op.spread_brl == D("-687.52") and op.spread_pct == D("-0.015523")


def test_no_attachment_fails(tmp_path):
    with pytest.raises(LayoutError, match="anexo"):
        ler_ponte(_eml(tmp_path, []))


def test_two_attachments_fail(tmp_path):
    with pytest.raises(LayoutError, match="anexo"):
        ler_ponte(_eml(tmp_path, [_xlsx([OP]), _xlsx([OP])]))


def test_missing_column_fails_naming_it(tmp_path):
    cab = [c for c in CAB if c != "Spread R$"]
    linha = [v for v, c in zip(OP, CAB) if c != "Spread R$"]
    with pytest.raises(LayoutError, match="Spread R\\$"):
        ler_ponte(_eml(tmp_path, [_xlsx([linha], cab=cab)]))


def test_missing_operations_sheet_fails(tmp_path):
    with pytest.raises(LayoutError, match="Operações"):
        ler_ponte(_eml(tmp_path, [_xlsx([OP], sheet="Outra")]))


def test_text_dates_dd_mm_yyyy_are_accepted(tmp_path):
    l = [OP[0], "30/09/2026", "01/10/2026", *OP[3:]]
    (op,) = ler_ponte(_eml(tmp_path, [_xlsx([l])]))
    assert op.data_contratacao == date(2026, 9, 30)


def test_real_file_golden(dados):
    ops = ler_ponte(dados / "03_email_ponte_cambio_relatorio_set2026.eml")
    assert len(ops) == 233 and len({o.n_operacao for o in ops}) == 232
    assert sum(1 for o in ops if o.spread_brl < 0) == 4
    assert sum(1 for o in ops if o.status == "APROVADO C/ RESSALVA") == 16
    assert sum((o.spread_brl for o in ops), D(0)) == D("78073.59")  # o rodapé da Ponte conta a duplicata


def test_real_file_ledger_only_has_the_two_footer_rows(dados):
    from tarvo.core.ledger import Ledger

    ledger = Ledger()
    ler_ponte(dados / "03_email_ponte_cambio_relatorio_set2026.eml", ledger)
    assert ledger.contar("Ponte", "rodapé ou linha sem dado") == 2


def _linha_dado(n_op):
    return [n_op, *OP[1:]]


def test_row_with_data_but_unknown_prefix_fails_loudly(tmp_path):
    with pytest.raises(LayoutError, match="linha 7.*PX-0926-0300.*PC-"):
        ler_ponte(_eml(tmp_path, [_xlsx([OP, _linha_dado("PX-0926-0300")])]))


def test_row_with_data_and_empty_operation_number_fails_loudly(tmp_path):
    with pytest.raises(LayoutError, match="linha 7"):
        ler_ponte(_eml(tmp_path, [_xlsx([OP, _linha_dado(None)])]))


def test_footer_with_numbers_in_other_columns_is_not_flagged(tmp_path):
    # o rodapé real tem 233 e 78073.59 na coluna B; só CNPJ, Valor ME e Spread R$ denunciam operação
    ops = ler_ponte(_eml(tmp_path, [_xlsx([OP])]))
    assert len(ops) == 1


def test_footer_rows_are_counted_in_the_ledger_but_blank_rows_are_not(tmp_path):
    from tarvo.core.ledger import Ledger

    ledger = Ledger()
    ler_ponte(_eml(tmp_path, [_xlsx([OP])]), ledger)
    assert ledger.contar("Ponte", "rodapé ou linha sem dado") == 2  # "Total de operações" e "Spread total R$"
