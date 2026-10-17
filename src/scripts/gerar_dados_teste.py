"""Gera um pacote mínimo (1 lojista, 1 pendência) para testar o fluxo de ponta a ponta.

    python src/scripts/gerar_dados_teste.py [pasta_saida]

Competência 2026-10 (os alertas fixos do config valem só para 2026-09).
Lojista: Trilha Jovem Turismo (EC 1068443135), taxas corretas. A única pendência esperada é um
PIX recebido sem identificação no Aurora (LANCAMENTO_SEM_ORIGEM).
"""
import io
import sys
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal as D
from pathlib import Path

import openpyxl

SAIDA = Path(sys.argv[1] if len(sys.argv) > 1 else "dados_teste")
EC, NOME, CNPJ = "1068443135", "TRILHA JOVEM TURISMO", "21394880000106"
TAXAS = {"DEBITO": D("1.49"), "CREDITO A VISTA": D("2.69"), "CREDITO PARCELADO": D("3.19")}
# (id, dia, modalidade, parcelas, bruto)
VENDAS = [
    ("TX90000001", 1, "DEBITO", 1, "250.00"), ("TX90000002", 1, "CREDITO A VISTA", 1, "1200.00"),
    ("TX90000003", 2, "CREDITO PARCELADO", 3, "3000.00"), ("TX90000004", 3, "CREDITO A VISTA", 1, "845.50"),
    ("TX90000005", 4, "DEBITO", 1, "99.90"), ("TX90000006", 8, "CREDITO A VISTA", 1, "2150.00"),
    ("TX90000007", 9, "CREDITO PARCELADO", 2, "1780.40"), ("TX90000008", 10, "DEBITO", 1, "430.00"),
]


def q(v):
    return v.quantize(D("0.01"), ROUND_HALF_UP)


def br(v):
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def orbe():
    linhas = ["id_transacao;data_movimento;cod_estabelecimento;nome_estabelecimento;tipo_lancamento;modalidade;"
              "qtd_parcelas;bandeira;valor_bruto;taxa_aplicada_pct;valor_taxa;valor_liquido;id_referencia;data_venda_original"]
    total_liq = D(0)
    for id_, dia, mod, parc, bruto in VENDAS:
        b, t = D(bruto), TAXAS[mod]
        taxa = q(b * t / 100)
        total_liq += b - taxa
        linhas.append(f"{id_};{dia:02d}/10/2026;{EC};{NOME};VENDA;{mod};{parc};VISA;{br(b).replace('.', '')};"
                      f"{str(t).replace('.', ',')};{br(taxa).replace('.', '')};{br(b - taxa).replace('.', '')};;")
    return "\r\n".join(linhas) + "\r\n", total_liq


def taxas():
    # a planilha real inteira: o config de fábrica (ecs_extra, overrides) referencia CNPJs dela
    src = Path("dados/02_tabela_taxas_contratadas.xlsx")
    (SAIDA / src.name).write_bytes(src.read_bytes())


def ponte():
    from email.message import EmailMessage
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Operações"
    ws.append(["PONTE CÂMBIO S.A. - Relatório Mensal de Operações por Parceiro"])
    ws.append(["Parceiro: TARVO PAGAMENTOS LTDA  |  CNPJ 84.626.315/0001-39"])
    ws.append(["Competência: 10/2026  |  Gerado em 02/11/2026 07:12"])
    ws.append([])
    ws.append(["Nº Operação", "Data Contratação", "Data Liquidação", "CNPJ Cliente", "Cliente", "Moeda", "Valor ME",
               "Taxa Cliente", "PTAX Ref.", "Valor R$", "Spread R$", "Spread %", "Spread Estimado R$ (D-1)",
               "IOF R$", "Status Compliance", "Observação"])
    buf = io.BytesIO()
    wb.save(buf)
    m = EmailMessage()
    m["From"], m["To"] = "relatorios@pontecambio.com.br", "financeiro@tarvo.com.br"
    m["Date"], m["Subject"] = "Mon, 02 Nov 2026 07:15:03 -0300", "Relatório mensal de operações - TARVO - 10/2026"
    m.set_content("Segue em anexo o relatório mensal de operações de câmbio referente à competência 10/2026.\n"
                  "Nenhuma operação do parceiro no período.\n")
    m.add_attachment(buf.getvalue(), maintype="application",
                     subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     filename="PonteCambio_Relatorio_TARVO_102026.xlsx")
    (SAIDA / "03_email_ponte_cambio_relatorio_out2026.eml").write_bytes(bytes(m))


def aurora(total_liq):
    ted = total_liq
    pix_repasse = q(total_liq * D("0.97"))  # repasse ao lojista (valor ilustrativo)
    saldo = D("500000.00")
    linhas = ["Banco Aurora S.A.;;;;", "Extrato de Conta Corrente - Pessoa Jurídica;;;;",
              "Cliente: TARVO PAGAMENTOS LTDA;CNPJ: 84.626.315/0001-39;;;", "Agência: 0318;Conta: 4471-0;;;",
              "Período: 01/10/2026 a 31/10/2026;;;;", ";;;;", "Data;Lançamento;Documento;Valor (R$);Saldo (R$)",
              f"30/09/2026;SALDO ANTERIOR;;;{br(saldo)}"]
    movs = [("09/10/2026", "TED RECEBIDA 99.876.669/0001-09 ORBE ADQUIRENCIA SA", "700001", ted),
            ("10/10/2026", "PIX ENVIADO TRILHA JOVEM TURISMO LTDA", "", -pix_repasse),
            ("16/10/2026", "PIX RECEBIDO 38686002000180 SEM IDENTIFICACAO", "", D("7350.00")),
            ("31/10/2026", "TAR PACOTE SERVICOS PJ", "", D("-389.00"))]
    for data, desc, doc, v in movs:
        saldo += v
        linhas.append(f"{data};{desc};{doc};{br(v)};{br(saldo)}")
    linhas += [";;;;", f";SALDO FINAL;;;{br(saldo)}", ";Os lançamentos estão sujeitos a confirmação.;;;"]
    (SAIDA / "05a_extrato_banco_aurora_cc4471_out2026.csv").write_text("\n".join(linhas) + "\n", encoding="utf-8")


def meridiano():
    ofx = """OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
<SIGNONMSGSRSV1>
<SONRS>
<STATUS>
<CODE>0
<SEVERITY>INFO
</STATUS>
<DTSERVER>20261001063000[-3:BRT]
<LANGUAGE>POR
</SONRS>
</SIGNONMSGSRSV1>
<BANKMSGSRSV1>
<STMTTRNRS>
<TRNUID>1001
<STATUS>
<CODE>0
<SEVERITY>INFO
</STATUS>
<STMTRS>
<CURDEF>BRL
<BANKACCTFROM>
<BANKID>0477
<BRANCHID>0091
<ACCTID>90233-5
<ACCTTYPE>CHECKING
</BANKACCTFROM>
<BANKTRANLIST>
<DTSTART>20261001000000[-3:BRT]
<DTEND>20261031235959[-3:BRT]
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20261031120000[-3:BRT]
<TRNAMT>-450.00
<FITID>MRD2026100696
<CHECKNUM>470986
<MEMO>TARIFA PACOTE CAMBIO
</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL>
<BALAMT>99550.00
<DTASOF>20261031235959[-3:BRT]
</LEDGERBAL>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""
    (SAIDA / "05b_extrato_banco_meridiano_cc90233_out2026.ofx").write_text(ofx, encoding="cp1252")


def plano():
    src = Path("dados/04_plano_de_contas_fenix_erp.csv")
    (SAIDA / src.name).write_bytes(src.read_bytes())


if __name__ == "__main__":
    SAIDA.mkdir(parents=True, exist_ok=True)
    csv, liq = orbe()
    (SAIDA / "01_orbe_relatorio_comissoes_out2026.csv").write_bytes(csv.encode("utf-8"))
    taxas(), ponte(), aurora(liq), meridiano(), plano()
    print(f"gerado em {SAIDA}/")
