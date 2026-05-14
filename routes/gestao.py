from flask import Blueprint, render_template, request, redirect, flash
from utils.auth import gestao_required
from models.lancamento_financeiro import LancamentoFinanceiro
from database import db
from datetime import datetime
from collections import Counter


gestao_bp = Blueprint("gestao", __name__, url_prefix="/gestao")


def dinheiro(valor):
    try:
        return float(valor or 0)
    except Exception:
        return 0


def normalizar_texto(valor):
    if not valor:
        return None
    return valor.strip().upper()


def parse_data(data_str):
    if not data_str:
        return None
    return datetime.strptime(data_str, "%Y-%m-%d").date()


@gestao_bp.route("/")
@gestao_required
def index():
    return redirect("/gestao/dashboard")


# =========================================================
# DASHBOARD FINANCEIRO
# =========================================================
@gestao_bp.route("/dashboard")
@gestao_required
def dashboard():

    hoje = datetime.now()

    mes = request.args.get("mes", type=int) or hoje.month
    ano = request.args.get("ano", type=int) or hoje.year

    lancamentos = LancamentoFinanceiro.query.filter_by(
        mes=mes,
        ano=ano
    ).all()

    total_entradas = 0
    total_saidas = 0
    total_a_pagar = 0
    total_a_receber = 0

    despesas_counter = Counter()
    receitas_counter = Counter()
    clientes_counter = Counter()

    for l in lancamentos:

        valor = dinheiro(l.valor)
        tipo = (l.tipo or "").upper()
        status = (l.status or "").upper()

        if tipo == "RECEITA":

            if status in ["RECEBIDO", "OK"]:
                total_entradas += valor
            elif status not in ["CANCELADO"]:
                total_a_receber += valor

            receitas_counter[l.categoria or "SEM CATEGORIA"] += valor

            if l.cliente:
                clientes_counter[l.cliente] += valor

        elif tipo == "DESPESA":

            if status in ["PAGO", "OK"]:
                total_saidas += valor
            elif status not in ["CANCELADO"]:
                total_a_pagar += valor

            despesas_counter[l.categoria or "SEM CATEGORIA"] += valor

    saldo_inicial = 0
    lucro_mes = total_entradas - total_saidas
    saldo_final = saldo_inicial + total_entradas - total_saidas

    margem_operacional = 0
    if total_entradas > 0:
        margem_operacional = (lucro_mes / total_entradas) * 100

    return render_template(
        "gestao/dashboard.html",
        mes=mes,
        ano=ano,

        saldo_inicial=saldo_inicial,
        total_entradas=total_entradas,
        total_saidas=total_saidas,
        lucro_mes=lucro_mes,
        saldo_final=saldo_final,
        total_a_pagar=total_a_pagar,
        total_a_receber=total_a_receber,
        margem_operacional=margem_operacional,

        ranking_despesas=despesas_counter.most_common(10),
        ranking_receitas=receitas_counter.most_common(10),
        ranking_clientes=clientes_counter.most_common(10)
    )


# =========================================================
# LISTAR LANÇAMENTOS
# =========================================================
@gestao_bp.route("/lancamentos")
@gestao_required
def lancamentos():

    query = LancamentoFinanceiro.query

    mes = request.args.get("mes", type=int)
    ano = request.args.get("ano", type=int)
    tipo = request.args.get("tipo")
    status = request.args.get("status")
    categoria = request.args.get("categoria")

    if mes:
        query = query.filter(LancamentoFinanceiro.mes == mes)

    if ano:
        query = query.filter(LancamentoFinanceiro.ano == ano)

    if tipo:
        query = query.filter(LancamentoFinanceiro.tipo == tipo)

    if status:
        query = query.filter(LancamentoFinanceiro.status == status)

    if categoria:
        query = query.filter(
            LancamentoFinanceiro.categoria.ilike(f"%{categoria}%")
        )

    lancamentos = query.order_by(
        LancamentoFinanceiro.data.desc(),
        LancamentoFinanceiro.id.desc()
    ).all()

    return render_template(
        "gestao/lancamentos.html",
        lancamentos=lancamentos,
        mes=mes,
        ano=ano,
        tipo=tipo,
        status=status,
        categoria=categoria
    )


# =========================================================
# NOVO LANÇAMENTO
# =========================================================
@gestao_bp.route("/lancamentos/novo", methods=["GET", "POST"])
@gestao_required
def novo_lancamento():

    if request.method == "POST":

        data = parse_data(request.form.get("data"))

        if not data:
            flash("Informe uma data válida.", "danger")
            return redirect("/gestao/lancamentos/novo")

        lancamento = LancamentoFinanceiro(
            data=data,
            tipo=normalizar_texto(request.form.get("tipo")),
            categoria=normalizar_texto(request.form.get("categoria")),
            subcategoria=normalizar_texto(request.form.get("subcategoria")),
            setor=normalizar_texto(request.form.get("setor")),
            cliente=normalizar_texto(request.form.get("cliente")),
            descricao=request.form.get("descricao"),
            valor=request.form.get("valor") or 0,
            status=normalizar_texto(request.form.get("status")),
            origem=normalizar_texto(request.form.get("origem")),
            recorrente=True if request.form.get("recorrente") == "on" else False,
            mes=data.month,
            ano=data.year
        )

        db.session.add(lancamento)
        db.session.commit()

        flash("Lançamento criado com sucesso!", "success")
        return redirect("/gestao/lancamentos")

    return render_template(
        "gestao/form_lancamento.html",
        lancamento=None
    )


# =========================================================
# EDITAR LANÇAMENTO
# =========================================================
@gestao_bp.route("/lancamentos/editar/<int:id>", methods=["GET", "POST"])
@gestao_required
def editar_lancamento(id):

    lancamento = LancamentoFinanceiro.query.get_or_404(id)

    if request.method == "POST":

        data = parse_data(request.form.get("data"))

        if not data:
            flash("Informe uma data válida.", "danger")
            return redirect(f"/gestao/lancamentos/editar/{id}")

        lancamento.data = data
        lancamento.tipo = normalizar_texto(request.form.get("tipo"))
        lancamento.categoria = normalizar_texto(request.form.get("categoria"))
        lancamento.subcategoria = normalizar_texto(request.form.get("subcategoria"))
        lancamento.setor = normalizar_texto(request.form.get("setor"))
        lancamento.cliente = normalizar_texto(request.form.get("cliente"))
        lancamento.descricao = request.form.get("descricao")
        lancamento.valor = request.form.get("valor") or 0
        lancamento.status = normalizar_texto(request.form.get("status"))
        lancamento.origem = normalizar_texto(request.form.get("origem"))
        lancamento.recorrente = True if request.form.get("recorrente") == "on" else False
        lancamento.mes = data.month
        lancamento.ano = data.year

        db.session.commit()

        flash("Lançamento atualizado com sucesso!", "success")
        return redirect("/gestao/lancamentos")

    return render_template(
        "gestao/form_lancamento.html",
        lancamento=lancamento
    )


# =========================================================
# EXCLUIR LANÇAMENTO
# =========================================================
@gestao_bp.route("/lancamentos/excluir/<int:id>")
@gestao_required
def excluir_lancamento(id):

    lancamento = LancamentoFinanceiro.query.get_or_404(id)

    db.session.delete(lancamento)
    db.session.commit()

    flash("Lançamento excluído com sucesso!", "success")
    return redirect("/gestao/lancamentos")