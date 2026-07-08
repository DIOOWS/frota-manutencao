from datetime import date, datetime
from decimal import Decimal

from flask import Blueprint, render_template, request, jsonify, send_file
from sqlalchemy import or_
from io import BytesIO
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from database import db
from utils.auth import gestao_required

from models.conta_pagar_importada import ContaPagarImportada
from models.planejamento_financeiro import PlanejamentoFinanceiro

from .radar_financeiro import (
    moeda,
    nome_mes,
    primeiro_dia_mes,
    ultimo_dia_mes,
    fim_dia_datetime,
)


planejamento_financeiro_bp = Blueprint(
    "planejamento_financeiro",
    __name__,
    url_prefix="/gestao/planejamento-financeiro",
)


def dinheiro_decimal(valor):
    if valor is None or valor == "":
        return Decimal("0")

    try:
        return Decimal(str(valor))
    except Exception:
        return Decimal("0")


def data_para_date_local(valor):
    if not valor:
        return None

    if isinstance(valor, datetime):
        return valor.date()

    if isinstance(valor, date):
        return valor

    texto = str(valor).strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(texto, formato).date()
        except Exception:
            pass

    return None


def formatar_data(valor):
    data_ref = data_para_date_local(valor)
    if not data_ref:
        return "-"

    return data_ref.strftime("%d/%m/%Y")


def texto_limpo(valor, padrao="-"):
    if valor is None:
        return padrao

    texto = str(valor).strip()
    return texto if texto else padrao


def buscar_primeiro(conta, campos, padrao="-"):
    for campo in campos:
        valor = getattr(conta, campo, None)
        if valor not in (None, ""):
            return texto_limpo(valor, padrao)

    return padrao


def conta_esta_cancelada(conta):
    status = texto_limpo(getattr(conta, "status", None), "").upper()
    return status in ("CANCELADO", "CANCELADA")


def conta_esta_paga_local(conta):
    if bool(getattr(conta, "pago", False)):
        return True

    status = texto_limpo(getattr(conta, "status", None), "").upper()
    return status in ("PAGO", "RECEBIDO", "OK", "QUITADO", "BAIXADO")


def montar_item_planejamento(conta, mes, ano, hoje):
    primeiro_mes = primeiro_dia_mes(mes, ano)
    ultimo_mes = ultimo_dia_mes(mes, ano)
    vencimento = data_para_date_local(getattr(conta, "data_vencimento", None))

    valor = dinheiro_decimal(getattr(conta, "valor", 0))

    conta_nome = buscar_primeiro(
        conta,
        [
            "plano_contas",
            "categoria",
            "descricao",
            "nome",
            "fornecedor_funcionario",
            "fornecedor",
        ],
        "SEM CONTA",
    )

    fornecedor = buscar_primeiro(
        conta,
        ["fornecedor_funcionario", "fornecedor", "cliente"],
        "-",
    )

    categoria = buscar_primeiro(
        conta,
        ["categoria", "plano_contas"],
        "-",
    )

    documento = buscar_primeiro(
        conta,
        ["numero_fatura", "documento", "numero_documento", "nf", "nota_fiscal"],
        "-",
    )

    observacao = buscar_primeiro(
        conta,
        ["observacoes", "observacao", "historico", "descricao"],
        "-",
    )

    parcela_label = buscar_primeiro(
        conta,
        ["parcela_label", "parcela", "numero_parcela"],
        "",
    )

    if parcela_label == "-":
        parcela_label = ""

    status_visual = "SEM DATA"
    is_herdada = False
    is_mes_atual = False
    dias_atraso = 0

    if vencimento:
        is_herdada = vencimento < primeiro_mes
        is_mes_atual = primeiro_mes <= vencimento <= ultimo_mes

        if vencimento < primeiro_mes:
            status_visual = "HERDADA"
        elif vencimento < hoje:
            status_visual = "ATRASADA"
        elif vencimento == hoje:
            status_visual = "VENCE HOJE"
        else:
            status_visual = "MÊS ATUAL"

        if vencimento < hoje:
            dias_atraso = (hoje - vencimento).days

    return {
        "id": int(getattr(conta, "id", 0)),
        "descricao": conta_nome,
        "conta_nome": conta_nome,
        "fornecedor": fornecedor,
        "categoria": categoria,
        "documento": documento,
        "observacao": observacao,
        "parcela_label": parcela_label,
        "vencimento": formatar_data(vencimento),
        "data_vencimento_obj": vencimento,
        "valor": valor,
        "valor_formatado": moeda(valor),
        "is_herdada": is_herdada,
        "is_mes_atual": is_mes_atual,
        "status_planejamento_visual": status_visual,
        "dias_atraso": dias_atraso,
    }


def buscar_contas_do_mes(mes, ano):
    """
    Busca todas as contas em aberto até o fim do mês selecionado.
    Isso inclui herdadas/atrasadas e contas do mês atual.
    Tudo vem em ordem de pagamento: vencimento mais antigo primeiro.
    """
    ultimo_mes = ultimo_dia_mes(mes, ano)

    return ContaPagarImportada.query.filter(
        ContaPagarImportada.origem_importacao == "DESPESA_COMPLETA",
        ContaPagarImportada.pago == False,
        or_(
            ContaPagarImportada.status.is_(None),
            ContaPagarImportada.status != "CANCELADO",
        ),
        ContaPagarImportada.data_vencimento <= fim_dia_datetime(ultimo_mes),
    ).order_by(
        ContaPagarImportada.data_vencimento.asc(),
        ContaPagarImportada.id.asc(),
    ).all()




def buscar_contas_exportacao_e_tela(mes, ano):
    """
    Busca contas até o fim da competência, incluindo pagas.
    Necessário para manter histórico: se uma conta planejada em julho foi paga no Radar,
    ela continua aparecendo/exportando em julho como PAGA.
    """
    ultimo_mes = ultimo_dia_mes(mes, ano)

    return ContaPagarImportada.query.filter(
        ContaPagarImportada.origem_importacao == "DESPESA_COMPLETA",
        or_(
            ContaPagarImportada.status.is_(None),
            ContaPagarImportada.status != "CANCELADO",
        ),
        ContaPagarImportada.data_vencimento <= fim_dia_datetime(ultimo_mes),
    ).order_by(
        ContaPagarImportada.data_vencimento.asc(),
        ContaPagarImportada.id.asc(),
    ).all()


def inicio_dia_datetime_local(data_ref):
    return datetime.combine(data_ref, datetime.min.time())


def conta_paga_na_competencia(conta, mes, ano):
    """
    Define se a conta paga no Radar pertence à competência do planejamento.
    Regra principal: data_pagamento dentro do mês/ano selecionado.
    Fallback: se não tiver data_pagamento, usa vencimento dentro do mês/ano.
    """
    primeiro_mes = primeiro_dia_mes(mes, ano)
    ultimo_mes = ultimo_dia_mes(mes, ano)

    data_pagamento = data_para_date_local(getattr(conta, "data_pagamento", None))
    if data_pagamento:
        return primeiro_mes <= data_pagamento <= ultimo_mes

    vencimento = data_para_date_local(getattr(conta, "data_vencimento", None))
    if vencimento:
        return primeiro_mes <= vencimento <= ultimo_mes

    return False


def sincronizar_pagas_do_radar(mes, ano):
    """
    Cria registros de planejamento para contas que já foram pagas no Radar
    dentro da competência selecionada. Assim elas aparecem como PAGA na tela
    e entram na aba Pagas da exportação, mesmo que não tenham sido planejadas
    manualmente antes.
    """
    primeiro_mes = primeiro_dia_mes(mes, ano)
    ultimo_mes = ultimo_dia_mes(mes, ano)

    inicio_dt = inicio_dia_datetime_local(primeiro_mes)
    fim_dt = fim_dia_datetime(ultimo_mes)

    contas = ContaPagarImportada.query.filter(
        ContaPagarImportada.origem_importacao == "DESPESA_COMPLETA",
        or_(
            ContaPagarImportada.data_pagamento >= inicio_dt,
            ContaPagarImportada.data_vencimento >= inicio_dt,
        ),
        or_(
            ContaPagarImportada.data_pagamento <= fim_dt,
            ContaPagarImportada.data_vencimento <= fim_dt,
        ),
    ).all()

    criadas = 0
    ja_existiam = 0

    for conta in contas:
        if conta_esta_cancelada(conta):
            continue

        if not conta_esta_paga_local(conta):
            continue

        if not conta_paga_na_competencia(conta, mes, ano):
            continue

        existe = PlanejamentoFinanceiro.query.filter_by(
            conta_id=int(getattr(conta, "id", 0)),
            origem="IMPORTADA",
            mes=mes,
            ano=ano,
        ).first()

        if existe:
            ja_existiam += 1
            continue

        novo = PlanejamentoFinanceiro(
            conta_id=int(getattr(conta, "id", 0)),
            origem="IMPORTADA",
            mes=mes,
            ano=ano,
            status_planejamento="SINCRONIZADA_RADAR",
        )
        db.session.add(novo)
        criadas += 1

    if criadas:
        db.session.commit()

    return criadas, ja_existiam

def buscar_planejamentos(mes, ano):
    registros = PlanejamentoFinanceiro.query.filter_by(
        origem="IMPORTADA",
        mes=mes,
        ano=ano,
    ).all()

    return {int(r.conta_id): r for r in registros}


@planejamento_financeiro_bp.route("/")
@gestao_required
def index():
    hoje = date.today()
    agora = datetime.now()

    mes = request.args.get("mes", type=int) or agora.month
    ano = request.args.get("ano", type=int) or agora.year

    if not 1 <= mes <= 12:
        mes = agora.month

    contas = buscar_contas_exportacao_e_tela(mes, ano)
    planejamentos = buscar_planejamentos(mes, ano)

    aguardando = []
    planejadas = []
    executadas = []

    for conta in contas:
        if conta_esta_cancelada(conta):
            continue

        item = montar_item_planejamento(conta, mes, ano, hoje)
        conta_id = int(item.get("id") or 0)

        if conta_id in planejamentos:
            if conta_esta_paga_local(conta):
                item["status_execucao"] = "PAGA"
                item["data_pagamento"] = formatar_data(getattr(conta, "data_pagamento", None))
                executadas.append(item)
            else:
                item["status_execucao"] = "PLANEJADA"
                item["data_pagamento"] = "-"
                planejadas.append(item)
        elif not conta_esta_paga_local(conta):
            item["status_execucao"] = "AGUARDANDO"
            item["data_pagamento"] = "-"
            aguardando.append(item)

    total_aguardando = sum(dinheiro_decimal(i.get("valor")) for i in aguardando)
    total_planejado = sum(dinheiro_decimal(i.get("valor")) for i in planejadas)
    total_executado = sum(dinheiro_decimal(i.get("valor")) for i in executadas)

    return render_template(
        "gestao/planejamento_financeiro.html",
        mes=mes,
        ano=ano,
        nome_mes=nome_mes,
        moeda=moeda,
        aguardando=aguardando,
        planejadas=planejadas,
        executadas=executadas,
        total_aguardando=total_aguardando,
        total_planejado=total_planejado,
        total_executado=total_executado,
    )




def montar_listas_planejamento(mes, ano):
    hoje = date.today()
    contas = buscar_contas_exportacao_e_tela(mes, ano)
    planejamentos = buscar_planejamentos(mes, ano)

    aguardando = []
    planejadas = []
    pagas = []

    for conta in contas:
        if conta_esta_cancelada(conta):
            continue

        item = montar_item_planejamento(conta, mes, ano, hoje)
        conta_id = int(item.get("id") or 0)
        item["data_pagamento"] = formatar_data(getattr(conta, "data_pagamento", None))

        if conta_id in planejamentos:
            if conta_esta_paga_local(conta):
                item["status_execucao"] = "PAGA"
                pagas.append(item)
            else:
                item["status_execucao"] = "PLANEJADA"
                planejadas.append(item)
        elif not conta_esta_paga_local(conta):
            item["status_execucao"] = "AGUARDANDO"
            aguardando.append(item)

    return aguardando, planejadas, pagas


def valor_decimal_item(item):
    return dinheiro_decimal(item.get("valor", 0))


def escrever_aba_planejamento(wb, titulo, competencia, itens, colunas):
    ws = wb.create_sheet(titulo)

    azul = "0B4EDB"
    azul_escuro = "061B3D"
    cinza = "F4F7FB"
    branco = "FFFFFF"
    borda_cor = "DCE5F1"

    border = Border(
        left=Side(style="thin", color=borda_cor),
        right=Side(style="thin", color=borda_cor),
        top=Side(style="thin", color=borda_cor),
        bottom=Side(style="thin", color=borda_cor),
    )

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(colunas))
    ws.cell(row=1, column=1).value = f"{titulo.upper()} - {competencia}"
    ws.cell(row=1, column=1).font = Font(bold=True, color=branco, size=14)
    ws.cell(row=1, column=1).fill = PatternFill("solid", fgColor=azul_escuro)
    ws.cell(row=1, column=1).alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 28

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(colunas))
    ws.cell(row=2, column=1).value = f"Exportado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')} | Total: {len(itens)} conta(s) | Valor: {moeda(sum(valor_decimal_item(i) for i in itens))}"
    ws.cell(row=2, column=1).font = Font(bold=True, color=azul_escuro, size=10)
    ws.cell(row=2, column=1).fill = PatternFill("solid", fgColor=cinza)
    ws.cell(row=2, column=1).alignment = Alignment(horizontal="center", vertical="center")

    for col_idx, (cabecalho, _) in enumerate(colunas, start=1):
        cell = ws.cell(row=4, column=col_idx)
        cell.value = cabecalho
        cell.font = Font(bold=True, color=branco)
        cell.fill = PatternFill("solid", fgColor=azul)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border

    linha = 5
    for item in itens:
        for col_idx, (_, chave) in enumerate(colunas, start=1):
            valor = item.get(chave, "-")
            if chave == "valor":
                valor = float(valor_decimal_item(item))
            cell = ws.cell(row=linha, column=col_idx)
            cell.value = valor
            cell.border = border
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            if chave == "valor":
                cell.number_format = 'R$ #,##0.00'
                cell.alignment = Alignment(horizontal="right", vertical="center")
        linha += 1

    linha_total = linha + 1
    ws.cell(row=linha_total, column=1).value = "TOTAL"
    ws.cell(row=linha_total, column=1).font = Font(bold=True, color=azul_escuro)
    ws.cell(row=linha_total, column=len(colunas)).value = float(sum(valor_decimal_item(i) for i in itens))
    ws.cell(row=linha_total, column=len(colunas)).number_format = 'R$ #,##0.00'
    ws.cell(row=linha_total, column=len(colunas)).font = Font(bold=True, color=azul_escuro)

    larguras = {
        "Status": 18,
        "Vencimento": 14,
        "Pago em": 14,
        "Conta": 38,
        "Fornecedor": 34,
        "Observação": 45,
        "Valor": 16,
        "Origem": 16,
        "Parcela": 12,
    }
    for col_idx, (cabecalho, _) in enumerate(colunas, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = larguras.get(cabecalho, 18)

    ws.freeze_panes = "A5"
    ws.auto_filter.ref = f"A4:{get_column_letter(len(colunas))}{max(4, linha - 1)}"
    return ws



@planejamento_financeiro_bp.route("/sincronizar-radar", methods=["POST"])
@gestao_required
def sincronizar_radar():
    agora = datetime.now()
    mes = request.form.get("mes", type=int) or agora.month
    ano = request.form.get("ano", type=int) or agora.year

    if not 1 <= mes <= 12:
        mes = agora.month

    try:
        criadas, ja_existiam = sincronizar_pagas_do_radar(mes, ano)
        return jsonify({
            "ok": True,
            "message": f"Sincronização concluída. {criadas} conta(s) paga(s) adicionada(s), {ja_existiam} já existiam.",
            "criadas": criadas,
            "ja_existiam": ja_existiam,
        })
    except Exception as erro:
        db.session.rollback()
        return jsonify({
            "ok": False,
            "message": f"Erro ao sincronizar Radar: {str(erro)}",
        }), 500

@planejamento_financeiro_bp.route("/exportar")
@gestao_required
def exportar_planejamento():
    agora = datetime.now()
    mes = request.args.get("mes", type=int) or agora.month
    ano = request.args.get("ano", type=int) or agora.year

    if not 1 <= mes <= 12:
        mes = agora.month

    aguardando, planejadas, pagas = montar_listas_planejamento(mes, ano)
    competencia = f"{nome_mes(mes)}/{ano}"

    wb = openpyxl.Workbook()
    ws_default = wb.active
    wb.remove(ws_default)

    colunas_base = [
        ("Status", "status_execucao"),
        ("Vencimento", "vencimento"),
        ("Conta", "conta_nome"),
        ("Fornecedor", "fornecedor"),
        ("Observação", "observacao"),
        ("Parcela", "parcela_label"),
        ("Valor", "valor"),
    ]

    colunas_pagas = [
        ("Status", "status_execucao"),
        ("Pago em", "data_pagamento"),
        ("Vencimento", "vencimento"),
        ("Conta", "conta_nome"),
        ("Fornecedor", "fornecedor"),
        ("Observação", "observacao"),
        ("Parcela", "parcela_label"),
        ("Valor", "valor"),
    ]

    escrever_aba_planejamento(wb, "Aguardando Decisão", competencia, aguardando, colunas_base)
    escrever_aba_planejamento(wb, "Planejadas", competencia, planejadas, colunas_base)
    escrever_aba_planejamento(wb, "Pagas", competencia, pagas, colunas_pagas)

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    nome_arquivo = f"planejamento_financeiro_{nome_mes(mes).lower()}_{ano}.xlsx".replace(" ", "_")

    return send_file(
        output,
        as_attachment=True,
        download_name=nome_arquivo,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@planejamento_financeiro_bp.route("/planejar/<int:conta_id>", methods=["POST"])
@gestao_required
def planejar(conta_id):
    mes = request.form.get("mes", type=int)
    ano = request.form.get("ano", type=int)

    if not mes or not ano:
        return jsonify({"ok": False, "message": "Mês e ano inválidos."}), 400

    existe = PlanejamentoFinanceiro.query.filter_by(
        conta_id=conta_id,
        origem="IMPORTADA",
        mes=mes,
        ano=ano,
    ).first()

    if not existe:
        novo = PlanejamentoFinanceiro(
            conta_id=conta_id,
            origem="IMPORTADA",
            mes=mes,
            ano=ano,
            status_planejamento="PLANEJADA",
        )
        db.session.add(novo)
        db.session.commit()

    return jsonify({"ok": True, "message": "Conta planejada para pagamento."})


@planejamento_financeiro_bp.route("/remover/<int:conta_id>", methods=["POST"])
@gestao_required
def remover(conta_id):
    mes = request.form.get("mes", type=int)
    ano = request.form.get("ano", type=int)

    if not mes or not ano:
        return jsonify({"ok": False, "message": "Mês e ano inválidos."}), 400

    registro = PlanejamentoFinanceiro.query.filter_by(
        conta_id=conta_id,
        origem="IMPORTADA",
        mes=mes,
        ano=ano,
    ).first()

    if registro:
        db.session.delete(registro)
        db.session.commit()

    return jsonify({"ok": True, "message": "Conta removida do planejamento."})
