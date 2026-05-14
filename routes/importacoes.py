from flask import Blueprint, render_template, request, redirect, flash
from utils.auth import gestao_required
from database import db
from models.conta_pagar_importada import ContaPagarImportada
from models.conta_receber_importada import ContaReceberImportada
from datetime import datetime
from decimal import Decimal
from io import BytesIO
import openpyxl

try:
    import pandas as pd
except Exception:
    pd = None


importacoes_bp = Blueprint(
    "importacoes",
    __name__,
    url_prefix="/gestao/importacoes"
)


# =========================================================
# CONFIGURAÇÃO DE ARQUIVOS
# =========================================================

EXTENSOES_PERMITIDAS = {"xlsx", "xlsm", "xls", "xlsb"}


# =========================================================
# HELPERS
# =========================================================

def texto(valor):
    if valor is None:
        return ""

    try:
        if pd is not None and pd.isna(valor):
            return ""
    except Exception:
        pass

    return str(valor).strip()


def extensao_arquivo(filename):
    if not filename or "." not in filename:
        return ""

    return filename.rsplit(".", 1)[1].lower().strip()


def arquivo_excel_valido(filename):
    return extensao_arquivo(filename) in EXTENSOES_PERMITIDAS


def normalizar_bool(valor):
    if valor is True:
        return True

    valor_txt = texto(valor).upper()

    return valor_txt in [
        "TRUE",
        "VERDADEIRO",
        "SIM",
        "S",
        "1",
        "PAGO",
        "OK",
        "RECEBIDO"
    ]


def normalizar_decimal(valor):
    if valor is None or texto(valor) == "":
        return Decimal("0.00")

    if isinstance(valor, (int, float, Decimal)):
        return Decimal(str(valor)).quantize(Decimal("0.01"))

    valor_txt = str(valor).strip()
    valor_txt = valor_txt.replace("R$", "")
    valor_txt = valor_txt.replace(".", "")
    valor_txt = valor_txt.replace(",", ".")
    valor_txt = valor_txt.strip()

    try:
        return Decimal(valor_txt).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def normalizar_data(valor):
    if not valor:
        return None

    if isinstance(valor, datetime):
        return valor

    formatos = [
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]

    valor_txt = texto(valor)

    for formato in formatos:
        try:
            return datetime.strptime(valor_txt, formato)
        except Exception:
            pass

    return None


def identificar_setor(plano_contas, receita=False):
    plano = texto(plano_contas).upper()

    if plano.endswith(" T"):
        return "LOGÍSTICA"

    if receita:
        return "GERAL"

    return "ASSISTÊNCIA"


def limpar_categoria(plano_contas):
    plano = texto(plano_contas)

    if plano.upper().endswith(" T"):
        return plano[:-2].strip()

    return plano


def achar_linha_cabecalho_openpyxl(sheet, primeira_coluna):
    primeira_coluna = primeira_coluna.upper()

    for row in sheet.iter_rows():
        valor = texto(row[0].value).upper()

        if valor == primeira_coluna:
            return row[0].row

    return None


def valor_por_coluna(row_dict, nome):
    return row_dict.get(nome, "")


def montar_linhas_openpyxl(sheet, header_row):
    headers = []

    for cell in sheet[header_row]:
        headers.append(texto(cell.value))

    linhas = []

    for row in sheet.iter_rows(min_row=header_row + 1, values_only=True):
        if not row or all(v is None or texto(v) == "" for v in row):
            continue

        item = {}

        for idx, header in enumerate(headers):
            if header:
                item[header] = row[idx] if idx < len(row) else None

        linhas.append(item)

    return linhas


def montar_linhas_pandas(conteudo, extensao, primeira_coluna):
    if pd is None:
        raise ImportError(
            "Para importar arquivos .xls ou .xlsb, instale pandas, xlrd e pyxlsb."
        )

    engine = None

    if extensao == "xls":
        engine = "xlrd"

    if extensao == "xlsb":
        engine = "pyxlsb"

    try:
        df_raw = pd.read_excel(
            BytesIO(conteudo),
            header=None,
            engine=engine
        )
    except Exception as e:
        raise ValueError(
            f"Não foi possível ler a planilha .{extensao}. "
            f"Verifique se o arquivo não está corrompido. Erro: {str(e)}"
        )

    header_index = None
    primeira_coluna = primeira_coluna.upper()

    for idx, row in df_raw.iterrows():
        primeiro_valor = texto(row.iloc[0]).upper()

        if primeiro_valor == primeira_coluna:
            header_index = idx
            break

    if header_index is None:
        raise ValueError("Cabeçalho não encontrado. A primeira coluna precisa conter 'Nº Fatura'.")

    headers = []

    for valor in df_raw.iloc[header_index].tolist():
        headers.append(texto(valor))

    linhas = []

    for _, row in df_raw.iloc[header_index + 1:].iterrows():
        valores = row.tolist()

        if all(texto(v) == "" for v in valores):
            continue

        item = {}

        for idx, header in enumerate(headers):
            if header:
                item[header] = valores[idx] if idx < len(valores) else None

        linhas.append(item)

    return linhas


def ler_linhas_upload(file_storage, primeira_coluna="Nº Fatura"):
    filename = file_storage.filename
    extensao = extensao_arquivo(filename)

    if not arquivo_excel_valido(filename):
        raise ValueError(
            "Formato não aceito. Envie uma planilha Excel nos formatos .xlsx, .xlsm, .xls ou .xlsb."
        )

    conteudo = file_storage.read()

    if not conteudo:
        raise ValueError("O arquivo enviado está vazio.")

    # .xlsx e .xlsm
    if extensao in ["xlsx", "xlsm"]:
        try:
            workbook = openpyxl.load_workbook(BytesIO(conteudo), data_only=True)
            sheet = workbook.active
        except Exception as e:
            raise ValueError(
                f"Não foi possível abrir a planilha .{extensao}. "
                f"Verifique se o arquivo é um Excel válido. Erro: {str(e)}"
            )

        header_row = achar_linha_cabecalho_openpyxl(sheet, primeira_coluna)

        if not header_row:
            raise ValueError("Cabeçalho não encontrado. A primeira coluna precisa conter 'Nº Fatura'.")

        return montar_linhas_openpyxl(sheet, header_row)

    # .xls e .xlsb
    if extensao in ["xls", "xlsb"]:
        return montar_linhas_pandas(conteudo, extensao, primeira_coluna)

    raise ValueError("Formato de planilha não suportado.")


def validar_mes_ano(mes, ano):
    if not mes or not ano:
        return False

    if mes < 1 or mes > 12:
        return False

    if ano < 2000:
        return False

    return True


# =========================================================
# TELA ÚNICA DE IMPORTAÇÕES
# =========================================================

@importacoes_bp.route("", strict_slashes=False)
@importacoes_bp.route("/", strict_slashes=False)
@gestao_required
def index():

    hoje = datetime.now()

    mes = request.args.get("mes", type=int) or hoje.month
    ano = request.args.get("ano", type=int) or hoje.year

    contas_pagar = ContaPagarImportada.query.filter_by(
        mes=mes,
        ano=ano
    ).order_by(
        ContaPagarImportada.data_vencimento.asc(),
        ContaPagarImportada.id.asc()
    ).all()

    contas_receber = ContaReceberImportada.query.filter_by(
        mes=mes,
        ano=ano
    ).order_by(
        ContaReceberImportada.data_vencimento.asc(),
        ContaReceberImportada.id.asc()
    ).all()

    total_pagar = sum([float(c.valor or 0) for c in contas_pagar])
    total_pagar_pago = sum([float(c.valor or 0) for c in contas_pagar if c.pago])
    total_pagar_pendente = sum([float(c.valor or 0) for c in contas_pagar if not c.pago])

    total_pagar_assistencia = sum([
        float(c.valor or 0) for c in contas_pagar
        if c.setor == "ASSISTÊNCIA"
    ])

    total_pagar_logistica = sum([
        float(c.valor or 0) for c in contas_pagar
        if c.setor == "LOGÍSTICA"
    ])

    total_receber = sum([float(c.total or c.valor or 0) for c in contas_receber])

    total_receber_pago = sum([
        float(c.total or c.valor or 0) for c in contas_receber
        if c.pago
    ])

    total_receber_pendente = sum([
        float(c.total or c.valor or 0) for c in contas_receber
        if not c.pago
    ])

    return render_template(
        "gestao/importacoes.html",

        mes=mes,
        ano=ano,

        contas_pagar=contas_pagar,
        contas_receber=contas_receber,

        total_pagar=total_pagar,
        total_pagar_pago=total_pagar_pago,
        total_pagar_pendente=total_pagar_pendente,
        total_pagar_assistencia=total_pagar_assistencia,
        total_pagar_logistica=total_pagar_logistica,

        total_receber=total_receber,
        total_receber_pago=total_receber_pago,
        total_receber_pendente=total_receber_pendente
    )


# =========================================================
# IMPORTAR CONTAS A PAGAR
# =========================================================

@importacoes_bp.route("/contas-a-pagar", methods=["POST"])
@gestao_required
def importar_contas_pagar():

    arquivo = request.files.get("arquivo_pagar")
    mes_importacao = request.form.get("mes_pagar", type=int)
    ano_importacao = request.form.get("ano_pagar", type=int)

    if not validar_mes_ano(mes_importacao, ano_importacao):
        flash("Informe mês e ano válidos para Contas a Pagar.", "danger")
        return redirect("/gestao/importacoes/")

    if not arquivo or not arquivo.filename:
        flash("Selecione uma planilha de Contas a Pagar.", "danger")
        return redirect(f"/gestao/importacoes/?mes={mes_importacao}&ano={ano_importacao}")

    if not arquivo_excel_valido(arquivo.filename):
        flash(
            "Formato não aceito. Envie uma planilha Excel nos formatos .xlsx, .xlsm, .xls ou .xlsb.",
            "danger"
        )
        return redirect(f"/gestao/importacoes/?mes={mes_importacao}&ano={ano_importacao}")

    try:
        linhas = ler_linhas_upload(arquivo, "Nº Fatura")

        ContaPagarImportada.query.filter_by(
            mes=mes_importacao,
            ano=ano_importacao
        ).delete()

        total_importado = 0

        for linha in linhas:
            plano_contas = texto(valor_por_coluna(linha, "Pl. Contas"))

            data_pagamento = normalizar_data(valor_por_coluna(linha, "Dt. Pgto"))
            data_vencimento = normalizar_data(valor_por_coluna(linha, "Dt. Vencto"))
            data_documento = normalizar_data(valor_por_coluna(linha, "Dt. Docto"))

            pago = normalizar_bool(valor_por_coluna(linha, "Pg?"))

            conta = ContaPagarImportada(
                numero_fatura=texto(valor_por_coluna(linha, "Nº Fatura")),
                fornecedor_funcionario=texto(valor_por_coluna(linha, "Fornecedor/Funcionário")),
                telefone=texto(valor_por_coluna(linha, "Telefone")),
                email=texto(valor_por_coluna(linha, "Email")),

                plano_contas=plano_contas,
                categoria=limpar_categoria(plano_contas),
                setor=identificar_setor(plano_contas, receita=False),

                data_documento=data_documento,
                data_vencimento=data_vencimento,
                data_pagamento=data_pagamento,

                valor=normalizar_decimal(valor_por_coluna(linha, "Valor")),

                pago=pago,
                status="PAGO" if pago else "PENDENTE",

                observacoes=texto(valor_por_coluna(linha, "Observações")),

                mes=mes_importacao,
                ano=ano_importacao,
            )

            db.session.add(conta)
            total_importado += 1

        db.session.commit()

        flash(
            f"Contas a Pagar de {mes_importacao:02d}/{ano_importacao} importadas com sucesso! {total_importado} linha(s).",
            "success"
        )

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao importar Contas a Pagar: {str(e)}", "danger")

    return redirect(f"/gestao/importacoes/?mes={mes_importacao}&ano={ano_importacao}")


# =========================================================
# IMPORTAR CONTAS A RECEBER
# =========================================================

@importacoes_bp.route("/contas-a-receber", methods=["POST"])
@gestao_required
def importar_contas_receber():

    arquivo = request.files.get("arquivo_receber")
    mes_importacao = request.form.get("mes_receber", type=int)
    ano_importacao = request.form.get("ano_receber", type=int)

    if not validar_mes_ano(mes_importacao, ano_importacao):
        flash("Informe mês e ano válidos para Contas a Receber.", "danger")
        return redirect("/gestao/importacoes/")

    if not arquivo or not arquivo.filename:
        flash("Selecione uma planilha de Contas a Receber.", "danger")
        return redirect(f"/gestao/importacoes/?mes={mes_importacao}&ano={ano_importacao}")

    if not arquivo_excel_valido(arquivo.filename):
        flash(
            "Formato não aceito. Envie uma planilha Excel nos formatos .xlsx, .xlsm, .xls ou .xlsb.",
            "danger"
        )
        return redirect(f"/gestao/importacoes/?mes={mes_importacao}&ano={ano_importacao}")

    try:
        linhas = ler_linhas_upload(arquivo, "Nº Fatura")

        ContaReceberImportada.query.filter_by(
            mes=mes_importacao,
            ano=ano_importacao
        ).delete()

        total_importado = 0

        for linha in linhas:
            plano_contas = texto(valor_por_coluna(linha, "Pl. Contas"))

            data_pagamento = normalizar_data(valor_por_coluna(linha, "Dt. Pgto"))
            data_vencimento = normalizar_data(valor_por_coluna(linha, "Dt. Vencto"))
            data_documento = normalizar_data(valor_por_coluna(linha, "Dt. Docto"))

            pago = normalizar_bool(valor_por_coluna(linha, "Pg?"))
            valor = normalizar_decimal(valor_por_coluna(linha, "Valor"))
            juros = normalizar_decimal(valor_por_coluna(linha, "Juros"))
            total = normalizar_decimal(valor_por_coluna(linha, "Total"))

            if total == Decimal("0.00"):
                total = valor + juros

            conta = ContaReceberImportada(
                numero_fatura=texto(valor_por_coluna(linha, "Nº Fatura")),
                cliente=texto(valor_por_coluna(linha, "Cliente")),
                telefone=texto(valor_por_coluna(linha, "Telefone")),
                email=texto(valor_por_coluna(linha, "Email")),

                plano_contas=plano_contas,
                categoria=limpar_categoria(plano_contas),
                setor=identificar_setor(plano_contas, receita=True),

                cobranca=texto(valor_por_coluna(linha, "Cobrança")),

                data_documento=data_documento,
                data_vencimento=data_vencimento,
                data_pagamento=data_pagamento,

                valor=valor,
                juros=juros,
                total=total,

                pago=pago,
                status="RECEBIDO" if pago else "PENDENTE",

                observacoes=texto(valor_por_coluna(linha, "Observações")),

                mes=mes_importacao,
                ano=ano_importacao,
            )

            db.session.add(conta)
            total_importado += 1

        db.session.commit()

        flash(
            f"Contas a Receber de {mes_importacao:02d}/{ano_importacao} importadas com sucesso! {total_importado} linha(s).",
            "success"
        )

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao importar Contas a Receber: {str(e)}", "danger")

    return redirect(f"/gestao/importacoes/?mes={mes_importacao}&ano={ano_importacao}")