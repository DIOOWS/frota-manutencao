import os
import calendar
from decimal import Decimal
from datetime import datetime, date, timedelta

from flask import Blueprint, render_template, request, redirect, flash, jsonify
from sqlalchemy import or_

from utils.auth import gestao_required
from database import db
from models.conta_radar_financeiro import ContaRadarFinanceiro
from services.telegram_service import (
    enviar_mensagem_telegram,
    montar_mensagem_contas_vencendo_hoje
)


radar_financeiro_bp = Blueprint(
    "radar_financeiro",
    __name__,
    url_prefix="/gestao/radar-financeiro"
)


# =========================================================
# HELPERS
# =========================================================

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

    if isinstance(valor, datetime):
        return valor.date()

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


def inicio_dia_datetime(data_ref):
    return datetime.combine(data_ref, datetime.min.time())


def fim_dia_datetime(data_ref):
    return datetime.combine(data_ref, datetime.max.time())


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


def ajustar_data_para_mes_ano(data_base, mes_destino, ano_destino):
    if not data_base:
        data_base = date.today()

    ultimo_destino = calendar.monthrange(ano_destino, mes_destino)[1]
    dia = min(data_base.day, ultimo_destino)

    return date(ano_destino, mes_destino, dia)


def data_conta_para_date(valor):
    if not valor:
        return None

    if isinstance(valor, datetime):
        return valor.date()

    if isinstance(valor, date):
        return valor

    return None


def redirect_radar(mes=None, ano=None):
    if mes and ano:
        return redirect(f"/gestao/radar-financeiro/?mes={mes}&ano={ano}")

    return redirect("/gestao/radar-financeiro/")


def criar_conta_radar(
    descricao,
    fornecedor,
    categoria,
    setor,
    valor,
    data_vencimento,
    status="PENDENTE",
    data_pagamento=None,
    observacoes="",
    parcela_atual=None,
    total_parcelas=None,
    recorrente=False,
    gerado_por_transporte=False,
    conta_origem_id=None
):
    conta = ContaRadarFinanceiro(
        descricao=descricao,
        fornecedor=fornecedor,
        categoria=categoria,
        setor=setor,
        valor=valor,

        data_vencimento=(
            datetime.combine(data_vencimento, datetime.min.time())
            if data_vencimento else None
        ),

        data_pagamento=(
            datetime.combine(data_pagamento, datetime.min.time())
            if data_pagamento else None
        ),

        status=status,
        observacoes=observacoes,

        parcela_atual=parcela_atual,
        total_parcelas=total_parcelas,

        recorrente=recorrente,
        gerado_por_transporte=gerado_por_transporte,
        conta_origem_id=conta_origem_id,

        mes=data_vencimento.month if data_vencimento else None,
        ano=data_vencimento.year if data_vencimento else None,
    )

    db.session.add(conta)

    return conta


def status_visual(conta, hoje):
    status = texto(conta.status).upper()

    if status == "PAGO":
        return {
            "label": "PAGO",
            "classe": "success",
            "grupo": "pagas"
        }

    if status == "CANCELADO":
        return {
            "label": "CANCELADO",
            "classe": "secondary",
            "grupo": "ocultas"
        }

    if status == "TRANSPORTADO":
        return {
            "label": "TRANSPORTADO",
            "classe": "info",
            "grupo": "ocultas"
        }

    data_vencimento = data_conta_para_date(conta.data_vencimento)

    if not data_vencimento:
        return {
            "label": "PENDENTE",
            "classe": "secondary",
            "grupo": "pendentes"
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
        "label": "PENDENTE",
        "classe": "dark",
        "grupo": "pendentes"
    }


def buscar_contas_vencendo_hoje(data_ref=None):
    if not data_ref:
        data_ref = date.today()

    inicio = inicio_dia_datetime(data_ref)
    fim = fim_dia_datetime(data_ref)

    contas = ContaRadarFinanceiro.query.filter(
        ContaRadarFinanceiro.data_vencimento >= inicio,
        ContaRadarFinanceiro.data_vencimento <= fim,
        ContaRadarFinanceiro.status.in_(["PENDENTE", "ADIADO"])
    ).order_by(
        ContaRadarFinanceiro.data_vencimento.asc(),
        ContaRadarFinanceiro.id.asc()
    ).all()

    return contas


def executar_envio_alerta_telegram_hoje():
    hoje = date.today()

    contas = buscar_contas_vencendo_hoje(hoje)

    if not contas:
        return {
            "ok": True,
            "enviado": False,
            "total_contas": 0,
            "mensagem": "Nenhuma conta pendente vencendo hoje."
        }

    mensagem = montar_mensagem_contas_vencendo_hoje(
        contas=contas,
        data_ref=hoje
    )

    sucesso, retorno = enviar_mensagem_telegram(mensagem)

    if sucesso:
        return {
            "ok": True,
            "enviado": True,
            "total_contas": len(contas),
            "mensagem": retorno
        }

    return {
        "ok": False,
        "enviado": False,
        "total_contas": len(contas),
        "mensagem": retorno
    }


# =========================================================
# RADAR FINANCEIRO MANUAL
# =========================================================

@radar_financeiro_bp.route("")
@radar_financeiro_bp.route("/")
@gestao_required
def index():

    hoje_dt = datetime.now()
    hoje = date.today()

    mes = request.args.get("mes", type=int) or hoje_dt.month
    ano = request.args.get("ano", type=int) or hoje_dt.year

    filtro = request.args.get("filtro", "todos").strip().lower()
    setor = request.args.get("setor", "").strip().upper()
    busca = request.args.get("busca", "").strip()

    visual = request.args.get("visual", "kanban").strip().lower()

    if visual not in ["kanban", "tabela"]:
        visual = "kanban"

    query = ContaRadarFinanceiro.query.filter(
        ContaRadarFinanceiro.mes == mes,
        ContaRadarFinanceiro.ano == ano
    )

    if setor:
        query = query.filter(
            ContaRadarFinanceiro.setor == setor
        )

    if busca:
        like = f"%{busca}%"

        query = query.filter(
            or_(
                ContaRadarFinanceiro.descricao.ilike(like),
                ContaRadarFinanceiro.fornecedor.ilike(like),
                ContaRadarFinanceiro.categoria.ilike(like),
                ContaRadarFinanceiro.observacoes.ilike(like),
            )
        )

    contas = query.order_by(
        ContaRadarFinanceiro.data_vencimento.asc().nullslast(),
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
    pendentes = [i for i in itens if i["grupo"] == "pendentes"]
    pagas = [i for i in itens if i["grupo"] == "pagas"]
    ocultas = [i for i in itens if i["grupo"] == "ocultas"]

    abertas = atrasadas + vence_hoje + proximas + pendentes

    if filtro == "abertas":
        itens_filtrados = abertas
    elif filtro == "atrasadas":
        itens_filtrados = atrasadas
    elif filtro == "hoje":
        itens_filtrados = vence_hoje
    elif filtro == "proximas":
        itens_filtrados = proximas
    elif filtro == "pendentes":
        itens_filtrados = pendentes
    elif filtro == "pagas":
        itens_filtrados = pagas
    else:
        itens_filtrados = abertas + pagas

    total_aberto = sum(dinheiro(i["conta"].valor) for i in abertas)
    total_atrasado = sum(dinheiro(i["conta"].valor) for i in atrasadas)
    total_hoje = sum(dinheiro(i["conta"].valor) for i in vence_hoje)
    total_proximas = sum(dinheiro(i["conta"].valor) for i in proximas)
    total_pendentes = sum(dinheiro(i["conta"].valor) for i in pendentes)
    total_pagas = sum(dinheiro(i["conta"].valor) for i in pagas)

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
        pendentes=pendentes,
        pagas=pagas,
        ocultas=ocultas,

        total_aberto=total_aberto,
        total_atrasado=total_atrasado,
        total_hoje=total_hoje,
        total_proximas=total_proximas,
        total_pendentes=total_pendentes,
        total_pagas=total_pagas,

        data_para_input=data_para_input
    )


# =========================================================
# TELEGRAM - ENVIO MANUAL
# =========================================================

@radar_financeiro_bp.route("/enviar-alerta-hoje", methods=["POST"])
@gestao_required
def enviar_alerta_telegram_hoje():

    try:
        resultado = executar_envio_alerta_telegram_hoje()

        if resultado["ok"] and resultado["enviado"]:
            flash(
                f"Alerta enviado no Telegram com {resultado['total_contas']} conta(s) vencendo hoje.",
                "success"
            )

        elif resultado["ok"] and not resultado["enviado"]:
            flash(
                resultado["mensagem"],
                "info"
            )

        else:
            flash(
                resultado["mensagem"],
                "danger"
            )

    except Exception as e:
        flash(
            f"Erro ao enviar alerta Telegram: {str(e)}",
            "danger"
        )

    return redirect(
        request.referrer or
        "/gestao/radar-financeiro"
    )


# =========================================================
# TELEGRAM - ENVIO AUTOMÁTICO PROTEGIDO
# Essa rota pode ser chamada por cron externo.
# =========================================================

@radar_financeiro_bp.route("/telegram/automatico", methods=["GET", "POST"])
def enviar_alerta_telegram_automatico():

    token_recebido = request.args.get("token") or request.form.get("token")
    token_correto = os.getenv("ALERTA_TELEGRAM_SECRET")

    if not token_correto:
        return jsonify({
            "ok": False,
            "erro": "ALERTA_TELEGRAM_SECRET não configurado no .env."
        }), 500

    if not token_recebido or token_recebido != token_correto:
        return jsonify({
            "ok": False,
            "erro": "Token inválido."
        }), 403

    try:
        resultado = executar_envio_alerta_telegram_hoje()

        status_code = 200 if resultado["ok"] else 500

        return jsonify(resultado), status_code

    except Exception as e:
        return jsonify({
            "ok": False,
            "enviado": False,
            "erro": str(e)
        }), 500


# =========================================================
# NOVA CONTA
# GERA PARCELAS AUTOMATICAMENTE
# =========================================================

@radar_financeiro_bp.route("/novo", methods=["POST"])
@gestao_required
def novo():

    try:
        descricao = texto(request.form.get("descricao"))
        fornecedor = texto(request.form.get("fornecedor"))
        categoria = texto(request.form.get("categoria"))
        setor = texto(request.form.get("setor")).upper() or "ASSISTÊNCIA"
        valor = normalizar_decimal(request.form.get("valor"))
        data_vencimento = parse_data(request.form.get("data_vencimento"))
        data_pagamento = parse_data(request.form.get("data_pagamento"))
        observacoes = texto(request.form.get("observacoes"))

        parcela_atual = request.form.get("parcela_atual", type=int)
        total_parcelas = request.form.get("total_parcelas", type=int)

        recorrente = True if request.form.get("recorrente") == "on" else False
        ja_pago = True if request.form.get("ja_pago") == "on" else False

        if not descricao:
            flash("Informe a descrição da conta.", "danger")
            return redirect(request.referrer or "/gestao/radar-financeiro")

        if not data_vencimento:
            flash("Informe uma data válida.", "danger")
            return redirect(request.referrer or "/gestao/radar-financeiro")

        if total_parcelas and total_parcelas < 1:
            total_parcelas = None

        if parcela_atual and parcela_atual < 1:
            parcela_atual = None

        if total_parcelas and not parcela_atual:
            parcela_atual = 1

        if parcela_atual and total_parcelas and parcela_atual > total_parcelas:
            flash("A parcela atual não pode ser maior que o total de parcelas.", "danger")
            return redirect(request.referrer or "/gestao/radar-financeiro")

        primeira_parcela = parcela_atual or None

        if total_parcelas and parcela_atual:
            quantidade_contas = total_parcelas - parcela_atual + 1
        else:
            quantidade_contas = 1

        conta_origem_id = None

        for indice in range(quantidade_contas):
            data_parcela = data_vencimento

            for _ in range(indice):
                data_parcela = adicionar_um_mes(data_parcela)

            numero_parcela = None

            if primeira_parcela:
                numero_parcela = primeira_parcela + indice

            status_conta = "PENDENTE"
            data_pagamento_conta = None

            if indice == 0 and ja_pago:
                status_conta = "PAGO"
                data_pagamento_conta = data_pagamento or date.today()

            conta = criar_conta_radar(
                descricao=descricao,
                fornecedor=fornecedor,
                categoria=categoria,
                setor=setor,
                valor=valor,
                data_vencimento=data_parcela,
                status=status_conta,
                data_pagamento=data_pagamento_conta,
                observacoes=observacoes,
                parcela_atual=numero_parcela,
                total_parcelas=total_parcelas,
                recorrente=recorrente,
                gerado_por_transporte=False,
                conta_origem_id=conta_origem_id
            )

            db.session.flush()

            if indice == 0:
                conta_origem_id = conta.id

        db.session.commit()

        if quantidade_contas > 1:
            flash(
                f"Conta adicionada! {quantidade_contas} parcela(s) gerada(s) automaticamente.",
                "success"
            )
        else:
            flash("Conta adicionada ao Radar Financeiro!", "success")

        return redirect_radar(data_vencimento.month, data_vencimento.year)

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao cadastrar conta: {str(e)}", "danger")

    return redirect(request.referrer or "/gestao/radar-financeiro")


# =========================================================
# EDITAR CONTA
# =========================================================

@radar_financeiro_bp.route("/editar/<int:id>", methods=["POST"])
@gestao_required
def editar(id):

    conta = ContaRadarFinanceiro.query.get_or_404(id)

    try:
        data_vencimento = parse_data(request.form.get("data_vencimento"))
        data_pagamento = parse_data(request.form.get("data_pagamento"))

        conta.descricao = texto(request.form.get("descricao"))
        conta.fornecedor = texto(request.form.get("fornecedor"))
        conta.categoria = texto(request.form.get("categoria"))
        conta.setor = texto(request.form.get("setor")).upper() or "ASSISTÊNCIA"
        conta.valor = normalizar_decimal(request.form.get("valor"))

        conta.data_vencimento = (
            datetime.combine(data_vencimento, datetime.min.time())
            if data_vencimento else None
        )

        conta.data_pagamento = (
            datetime.combine(data_pagamento, datetime.min.time())
            if data_pagamento else None
        )

        conta.status = texto(request.form.get("status")).upper() or "PENDENTE"

        if conta.status != "PAGO":
            conta.data_pagamento = None

        conta.observacoes = texto(request.form.get("observacoes"))
        conta.parcela_atual = request.form.get("parcela_atual", type=int)
        conta.total_parcelas = request.form.get("total_parcelas", type=int)
        conta.recorrente = True if request.form.get("recorrente") == "on" else False

        if data_vencimento:
            conta.mes = data_vencimento.month
            conta.ano = data_vencimento.year

        db.session.commit()

        flash("Conta atualizada com sucesso!", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao editar conta: {str(e)}", "danger")

    return redirect(request.referrer or "/gestao/radar-financeiro")


# =========================================================
# PAGAR CONTA
# =========================================================

@radar_financeiro_bp.route("/pagar/<int:id>", methods=["POST"])
@gestao_required
def pagar(id):

    conta = ContaRadarFinanceiro.query.get_or_404(id)

    data_pagamento = parse_data(request.form.get("data_pagamento"))

    if not data_pagamento:
        data_pagamento = date.today()

    try:
        conta.status = "PAGO"
        conta.data_pagamento = datetime.combine(data_pagamento, datetime.min.time())

        db.session.commit()

        flash("Conta marcada como paga!", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao marcar pagamento: {str(e)}", "danger")

    return redirect(request.referrer or "/gestao/radar-financeiro")


# =========================================================
# TRANSPORTAR CONTA INDIVIDUAL
# Mantido no backend para não quebrar registros antigos/botões antigos.
# A tela atual não exibe mais essa ação no menu.
# =========================================================

@radar_financeiro_bp.route("/transportar/<int:id>", methods=["POST"])
@gestao_required
def transportar(id):

    conta = ContaRadarFinanceiro.query.get_or_404(id)

    try:
        nova_data_str = request.form.get("nova_data_vencimento")
        nova_data = parse_data(nova_data_str)

        if not nova_data:
            data_base = data_conta_para_date(conta.data_vencimento) or date.today()
            nova_data = adicionar_um_mes(data_base)

        novo_valor = normalizar_decimal(request.form.get("valor") or conta.valor)
        observacao_extra = texto(request.form.get("observacoes"))

        nova_parcela_atual = None

        if conta.parcela_atual:
            nova_parcela_atual = conta.parcela_atual + 1

        if (
            conta.total_parcelas
            and nova_parcela_atual
            and nova_parcela_atual > conta.total_parcelas
        ):
            flash(
                "Essa conta já está na última parcela. Não é possível transportar para uma nova parcela.",
                "warning"
            )
            return redirect(request.referrer or "/gestao/radar-financeiro")

        criar_conta_radar(
            descricao=conta.descricao,
            fornecedor=conta.fornecedor,
            categoria=conta.categoria,
            setor=conta.setor,
            valor=novo_valor,
            data_vencimento=nova_data,
            status="PENDENTE",
            data_pagamento=None,
            observacoes=(observacao_extra or conta.observacoes),
            parcela_atual=nova_parcela_atual,
            total_parcelas=conta.total_parcelas,
            recorrente=conta.recorrente,
            gerado_por_transporte=True,
            conta_origem_id=conta.id
        )

        if conta.status != "PAGO":
            conta.status = "TRANSPORTADO"
            conta.data_pagamento = None

        db.session.commit()

        flash(
            f"Conta transportada para {nova_data.month:02d}/{nova_data.year} como PENDENTE!",
            "success"
        )

        return redirect_radar(nova_data.month, nova_data.year)

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao transportar conta: {str(e)}", "danger")

    return redirect(request.referrer or "/gestao/radar-financeiro")


# =========================================================
# TRANSPORTAR PAGAS EM LOTE
# A original continua PAGA no mês original.
# A nova nasce PENDENTE no mês escolhido.
# =========================================================

@radar_financeiro_bp.route("/transportar-pagas-lote", methods=["POST"])
@gestao_required
def transportar_pagas_lote():

    ids = request.form.getlist("contas_ids")
    mes_destino = request.form.get("mes_destino", type=int)
    ano_destino = request.form.get("ano_destino", type=int)

    if not ids:
        flash("Selecione pelo menos uma conta paga para transportar.", "warning")
        return redirect(request.referrer or "/gestao/radar-financeiro")

    if not mes_destino or not ano_destino or mes_destino < 1 or mes_destino > 12:
        flash("Informe mês e ano de destino válidos.", "danger")
        return redirect(request.referrer or "/gestao/radar-financeiro")

    try:
        contas = ContaRadarFinanceiro.query.filter(
            ContaRadarFinanceiro.id.in_(ids),
            ContaRadarFinanceiro.status == "PAGO"
        ).all()

        total_criadas = 0
        total_ignoradas = 0

        for conta in contas:
            data_base = data_conta_para_date(conta.data_vencimento) or date.today()

            nova_data = ajustar_data_para_mes_ano(
                data_base=data_base,
                mes_destino=mes_destino,
                ano_destino=ano_destino
            )

            nova_parcela_atual = None

            if conta.parcela_atual:
                nova_parcela_atual = conta.parcela_atual + 1

            if (
                conta.total_parcelas
                and nova_parcela_atual
                and nova_parcela_atual > conta.total_parcelas
            ):
                total_ignoradas += 1
                continue

            criar_conta_radar(
                descricao=conta.descricao,
                fornecedor=conta.fornecedor,
                categoria=conta.categoria,
                setor=conta.setor,
                valor=conta.valor,
                data_vencimento=nova_data,
                status="PENDENTE",
                data_pagamento=None,
                observacoes=conta.observacoes,
                parcela_atual=nova_parcela_atual,
                total_parcelas=conta.total_parcelas,
                recorrente=conta.recorrente,
                gerado_por_transporte=True,
                conta_origem_id=conta.id
            )

            total_criadas += 1

        db.session.commit()

        flash(
            f"{total_criadas} conta(s) transportada(s) como PENDENTE para {mes_destino:02d}/{ano_destino}. "
            f"Ignoradas por limite de parcela: {total_ignoradas}.",
            "success"
        )

        return redirect_radar(mes_destino, ano_destino)

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao transportar contas pagas em lote: {str(e)}", "danger")

    return redirect(request.referrer or "/gestao/radar-financeiro")


# =========================================================
# CANCELAR CONTA
# Mantido no backend para não quebrar registros antigos/botões antigos.
# A tela atual não exibe mais essa ação no menu.
# =========================================================

@radar_financeiro_bp.route("/cancelar/<int:id>", methods=["POST"])
@gestao_required
def cancelar(id):

    conta = ContaRadarFinanceiro.query.get_or_404(id)

    try:
        conta.status = "CANCELADO"

        db.session.commit()

        flash("Conta cancelada.", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao cancelar conta: {str(e)}", "danger")

    return redirect(request.referrer or "/gestao/radar-financeiro")


# =========================================================
# EXCLUIR CONTA
# =========================================================

@radar_financeiro_bp.route("/excluir/<int:id>", methods=["POST"])
@gestao_required
def excluir(id):

    conta = ContaRadarFinanceiro.query.get_or_404(id)

    try:
        db.session.delete(conta)
        db.session.commit()

        flash("Conta excluída.", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir conta: {str(e)}", "danger")

    return redirect(request.referrer or "/gestao/radar-financeiro")