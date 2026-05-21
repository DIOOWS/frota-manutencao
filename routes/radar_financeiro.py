from flask import Blueprint, render_template, request, redirect, flash
from utils.auth import gestao_required
from database import db
from models.conta_radar_financeiro import ContaRadarFinanceiro
from datetime import datetime, date, timedelta
from decimal import Decimal
import calendar


radar_financeiro_bp = Blueprint(
    "radar_financeiro",
    __name__,
    url_prefix="/gestao/radar-financeiro"
)


def texto(valor):
    if valor is None:
        return ""

    return str(valor).strip()


def normalizar_decimal(valor):
    if valor is None or texto(valor) == "":
        return Decimal("0.00")

    if isinstance(valor, (int, float, Decimal)):
        try:
            return Decimal(str(valor)).quantize(Decimal("0.01"))
        except Exception:
            return Decimal("0.00")

    valor_txt = str(valor).strip()
    valor_txt = valor_txt.replace("R$", "")
    valor_txt = valor_txt.replace(" ", "")

    if "," in valor_txt:
        valor_txt = valor_txt.replace(".", "")
        valor_txt = valor_txt.replace(",", ".")

    try:
        return Decimal(valor_txt).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def dinheiro(valor):
    try:
        return float(valor or 0)
    except Exception:
        return 0


def parse_data(valor):
    if not valor:
        return None

    if isinstance(valor, date):
        return valor

    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except Exception:
        return None


def data_para_input(valor):
    if not valor:
        return ""

    try:
        return valor.strftime("%Y-%m-%d")
    except Exception:
        return ""


def primeiro_dia_mes(mes, ano):
    return date(ano, mes, 1)


def ultimo_dia_mes(mes, ano):
    ultimo = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, ultimo)


def adicionar_um_mes(data_ref):
    mes = data_ref.month
    ano = data_ref.year

    if mes == 12:
        novo_mes = 1
        novo_ano = ano + 1
    else:
        novo_mes = mes + 1
        novo_ano = ano

    ultimo_novo_mes = calendar.monthrange(novo_ano, novo_mes)[1]
    novo_dia = min(data_ref.day, ultimo_novo_mes)

    return date(novo_ano, novo_mes, novo_dia)


def status_visual(conta, hoje):

    if conta.status == "PAGO":
        return {
            "label": "PAGO",
            "classe": "success",
            "grupo": "pagas"
        }

    if conta.status == "CANCELADO":
        return {
            "label": "CANCELADO",
            "classe": "secondary",
            "grupo": "canceladas"
        }

    if conta.status == "TRANSPORTADO":
        return {
            "label": "TRANSPORTADO",
            "classe": "info",
            "grupo": "transportadas"
        }

    data_vencimento = (
        conta.data_vencimento.date()
        if conta.data_vencimento else None
    )

    if not data_vencimento:
        return {
            "label": "SEM DATA",
            "classe": "secondary",
            "grupo": "sem_data"
        }

    if data_vencimento < hoje:
        return {
            "label": "ATRASADA",
            "classe": "danger",
            "grupo": "atrasadas"
        }

    if data_vencimento == hoje:
        return {
            "label": "VENCE HOJE",
            "classe": "warning",
            "grupo": "vence_hoje"
        }

    if data_vencimento <= hoje + timedelta(days=7):
        return {
            "label": "PRÓXIMOS 7 DIAS",
            "classe": "primary",
            "grupo": "proximas"
        }

    return {
        "label": "FUTURA",
        "classe": "dark",
        "grupo": "futuras"
    }


@radar_financeiro_bp.route("")
@radar_financeiro_bp.route("/")
@gestao_required
def index():

    hoje_dt = datetime.now()
    hoje = date.today()

    mes = request.args.get("mes", type=int) or hoje_dt.month
    ano = request.args.get("ano", type=int) or hoje_dt.year

    filtro = request.args.get(
        "filtro",
        "todos"
    ).strip().lower()

    setor = request.args.get(
        "setor",
        ""
    ).strip().upper()

    busca = request.args.get(
        "busca",
        ""
    ).strip()

    visual = request.args.get(
        "visual",
        "kanban"
    ).strip().lower()

    if visual not in ["kanban", "tabela"]:
        visual = "kanban"

    fim = datetime.combine(
        ultimo_dia_mes(mes, ano),
        datetime.max.time()
    )

    query = ContaRadarFinanceiro.query.filter(
        ContaRadarFinanceiro.data_vencimento <= fim
    )

    if setor:
        query = query.filter(
            ContaRadarFinanceiro.setor == setor
        )

    if busca:
        like = f"%{busca}%"

        query = query.filter(
            db.or_(
                ContaRadarFinanceiro.descricao.ilike(like),
                ContaRadarFinanceiro.fornecedor.ilike(like),
                ContaRadarFinanceiro.categoria.ilike(like),
                ContaRadarFinanceiro.observacoes.ilike(like),
            )
        )

    contas = query.order_by(
        ContaRadarFinanceiro.data_vencimento.asc(),
        ContaRadarFinanceiro.id.desc()
    ).all()

    itens = []

    for conta in contas:

        visual_status = status_visual(conta, hoje)

        itens.append({
            "conta": conta,
            "status_label": visual_status["label"],
            "status_classe": visual_status["classe"],
            "grupo": visual_status["grupo"],
        })

    atrasadas = [i for i in itens if i["grupo"] == "atrasadas"]
    vence_hoje = [i for i in itens if i["grupo"] == "vence_hoje"]
    proximas = [i for i in itens if i["grupo"] == "proximas"]
    futuras = [i for i in itens if i["grupo"] == "futuras"]
    pagas = [i for i in itens if i["grupo"] == "pagas"]
    transportadas = [i for i in itens if i["grupo"] == "transportadas"]
    canceladas = [i for i in itens if i["grupo"] == "canceladas"]

    abertas = [
        i for i in itens
        if i["conta"].status in ["PENDENTE", "ADIADO"]
    ]

    if filtro == "abertas":
        itens_filtrados = abertas

    elif filtro == "atrasadas":
        itens_filtrados = atrasadas

    elif filtro == "hoje":
        itens_filtrados = vence_hoje

    elif filtro == "proximas":
        itens_filtrados = proximas

    elif filtro == "futuras":
        itens_filtrados = futuras

    elif filtro == "pagas":
        itens_filtrados = pagas

    elif filtro == "transportadas":
        itens_filtrados = transportadas

    elif filtro == "canceladas":
        itens_filtrados = canceladas

    else:
        itens_filtrados = itens

    total_aberto = sum(
        dinheiro(i["conta"].valor)
        for i in abertas
    )

    total_atrasado = sum(
        dinheiro(i["conta"].valor)
        for i in atrasadas
    )

    total_hoje = sum(
        dinheiro(i["conta"].valor)
        for i in vence_hoje
    )

    total_proximas = sum(
        dinheiro(i["conta"].valor)
        for i in proximas
    )

    total_futuras = sum(
        dinheiro(i["conta"].valor)
        for i in futuras
    )

    total_pagas = sum(
        dinheiro(i["conta"].valor)
        for i in pagas
    )

    return render_template(
        "gestao/radar_financeiro.html",

        visual=visual,

        mes=mes,
        ano=ano,

        filtro=filtro,
        setor=setor,
        busca=busca,

        hoje=hoje,

        itens=itens,
        itens_filtrados=itens_filtrados,

        abertas=abertas,
        atrasadas=atrasadas,
        vence_hoje=vence_hoje,
        proximas=proximas,
        futuras=futuras,
        pagas=pagas,
        transportadas=transportadas,
        canceladas=canceladas,

        total_aberto=total_aberto,
        total_atrasado=total_atrasado,
        total_hoje=total_hoje,
        total_proximas=total_proximas,
        total_futuras=total_futuras,
        total_pagas=total_pagas,

        data_para_input=data_para_input
    )


@radar_financeiro_bp.route("/novo", methods=["POST"])
@gestao_required
def novo():

    try:

        descricao = texto(
            request.form.get("descricao")
        )

        fornecedor = texto(
            request.form.get("fornecedor")
        )

        categoria = texto(
            request.form.get("categoria")
        )

        setor = texto(
            request.form.get("setor")
        ).upper() or "ASSISTÊNCIA"

        valor = normalizar_decimal(
            request.form.get("valor")
        )

        data_vencimento = parse_data(
            request.form.get("data_vencimento")
        )

        observacoes = texto(
            request.form.get("observacoes")
        )

        parcela_atual = request.form.get(
            "parcela_atual",
            type=int
        )

        total_parcelas = request.form.get(
            "total_parcelas",
            type=int
        )

        recorrente = (
            True if request.form.get("recorrente") == "on"
            else False
        )

        if not descricao:
            flash(
                "Informe a descrição da conta.",
                "danger"
            )

            return redirect(
                request.referrer or
                "/gestao/radar-financeiro"
            )

        if not data_vencimento:
            flash(
                "Informe uma data válida.",
                "danger"
            )

            return redirect(
                request.referrer or
                "/gestao/radar-financeiro"
            )

        conta = ContaRadarFinanceiro(
            descricao=descricao,
            fornecedor=fornecedor,
            categoria=categoria,
            setor=setor,
            valor=valor,

            data_vencimento=datetime.combine(
                data_vencimento,
                datetime.min.time()
            ),

            status="PENDENTE",

            observacoes=observacoes,

            parcela_atual=parcela_atual,
            total_parcelas=total_parcelas,

            recorrente=recorrente,

            mes=data_vencimento.month,
            ano=data_vencimento.year,
        )

        db.session.add(conta)
        db.session.commit()

        flash(
            "Conta adicionada ao Radar Financeiro!",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        flash(
            f"Erro ao cadastrar conta: {str(e)}",
            "danger"
        )

    return redirect(
        request.referrer or
        "/gestao/radar-financeiro"
    )


@radar_financeiro_bp.route("/editar/<int:id>", methods=["POST"])
@gestao_required
def editar(id):

    conta = ContaRadarFinanceiro.query.get_or_404(id)

    try:

        data_vencimento = parse_data(
            request.form.get("data_vencimento")
        )

        data_pagamento = parse_data(
            request.form.get("data_pagamento")
        )

        conta.descricao = texto(
            request.form.get("descricao")
        )

        conta.fornecedor = texto(
            request.form.get("fornecedor")
        )

        conta.categoria = texto(
            request.form.get("categoria")
        )

        conta.setor = texto(
            request.form.get("setor")
        ).upper() or "ASSISTÊNCIA"

        conta.valor = normalizar_decimal(
            request.form.get("valor")
        )

        conta.data_vencimento = (
            datetime.combine(
                data_vencimento,
                datetime.min.time()
            )
            if data_vencimento else None
        )

        conta.data_pagamento = (
            datetime.combine(
                data_pagamento,
                datetime.min.time()
            )
            if data_pagamento else None
        )

        conta.status = texto(
            request.form.get("status")
        ).upper() or "PENDENTE"

        conta.observacoes = texto(
            request.form.get("observacoes")
        )

        conta.parcela_atual = request.form.get(
            "parcela_atual",
            type=int
        )

        conta.total_parcelas = request.form.get(
            "total_parcelas",
            type=int
        )

        conta.recorrente = (
            True if request.form.get("recorrente") == "on"
            else False
        )

        if data_vencimento:
            conta.mes = data_vencimento.month
            conta.ano = data_vencimento.year

        db.session.commit()

        flash(
            "Conta atualizada com sucesso!",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        flash(
            f"Erro ao editar conta: {str(e)}",
            "danger"
        )

    return redirect(
        request.referrer or
        "/gestao/radar-financeiro"
    )


@radar_financeiro_bp.route("/pagar/<int:id>", methods=["POST"])
@gestao_required
def pagar(id):

    conta = ContaRadarFinanceiro.query.get_or_404(id)

    data_pagamento = parse_data(
        request.form.get("data_pagamento")
    )

    if not data_pagamento:
        data_pagamento = date.today()

    try:

        conta.status = "PAGO"

        conta.data_pagamento = datetime.combine(
            data_pagamento,
            datetime.min.time()
        )

        db.session.commit()

        flash(
            "Conta marcada como paga!",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        flash(
            f"Erro ao marcar pagamento: {str(e)}",
            "danger"
        )

    return redirect(
        request.referrer or
        "/gestao/radar-financeiro"
    )


@radar_financeiro_bp.route("/transportar/<int:id>", methods=["POST"])
@gestao_required
def transportar(id):

    conta = ContaRadarFinanceiro.query.get_or_404(id)

    try:

        nova_data_str = request.form.get(
            "nova_data_vencimento"
        )

        nova_data = parse_data(
            nova_data_str
        )

        if not nova_data:

            data_base = (
                conta.data_vencimento.date()
                if conta.data_vencimento
                else date.today()
            )

            nova_data = adicionar_um_mes(
                data_base
            )

        novo_valor = normalizar_decimal(
            request.form.get("valor") or conta.valor
        )

        observacao_extra = texto(
            request.form.get("observacoes")
        )

        nova_parcela_atual = None

        if conta.parcela_atual:
            nova_parcela_atual = conta.parcela_atual + 1

        nova_conta = ContaRadarFinanceiro(

            descricao=conta.descricao,
            fornecedor=conta.fornecedor,
            categoria=conta.categoria,
            setor=conta.setor,

            valor=novo_valor,

            data_vencimento=datetime.combine(
                nova_data,
                datetime.min.time()
            ),

            status="PENDENTE",

            observacoes=(
                observacao_extra or
                conta.observacoes
            ),

            parcela_atual=nova_parcela_atual,
            total_parcelas=conta.total_parcelas,

            recorrente=conta.recorrente,

            gerado_por_transporte=True,

            conta_origem_id=conta.id,

            mes=nova_data.month,
            ano=nova_data.year,
        )

        conta.status = "TRANSPORTADO"

        db.session.add(nova_conta)
        db.session.commit()

        flash(
            "Conta transportada com sucesso!",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        flash(
            f"Erro ao transportar conta: {str(e)}",
            "danger"
        )

    return redirect(
        request.referrer or
        "/gestao/radar-financeiro"
    )


@radar_financeiro_bp.route("/cancelar/<int:id>", methods=["POST"])
@gestao_required
def cancelar(id):

    conta = ContaRadarFinanceiro.query.get_or_404(id)

    try:

        conta.status = "CANCELADO"

        db.session.commit()

        flash(
            "Conta cancelada.",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        flash(
            f"Erro ao cancelar conta: {str(e)}",
            "danger"
        )

    return redirect(
        request.referrer or
        "/gestao/radar-financeiro"
    )


@radar_financeiro_bp.route("/excluir/<int:id>", methods=["POST"])
@gestao_required
def excluir(id):

    conta = ContaRadarFinanceiro.query.get_or_404(id)

    try:

        db.session.delete(conta)

        db.session.commit()

        flash(
            "Conta excluída.",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        flash(
            f"Erro ao excluir conta: {str(e)}",
            "danger"
        )

    return redirect(
        request.referrer or
        "/gestao/radar-financeiro"
    )