from flask import Blueprint, render_template, request, redirect, flash
from utils.auth import gestao_required
from models.lancamento_financeiro import LancamentoFinanceiro
from models.fechamento_mensal import FechamentoMensal
from models.conta_pagar_importada import ContaPagarImportada
from models.conta_receber_importada import ContaReceberImportada
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


def mes_ano_anterior(mes, ano):
    if mes == 1:
        return 12, ano - 1

    return mes - 1, ano


def obter_fechamento_anterior(mes, ano):
    mes_ant, ano_ant = mes_ano_anterior(mes, ano)

    return FechamentoMensal.query.filter_by(
        mes=mes_ant,
        ano=ano_ant
    ).first()


def obter_saldo_inicial_automatico(mes, ano):
    fechamento_anterior = obter_fechamento_anterior(mes, ano)

    if fechamento_anterior:
        return dinheiro(fechamento_anterior.saldo_final)

    return 0


def obter_saldo_inicial_mes(mes, ano):
    fechamento_atual = FechamentoMensal.query.filter_by(
        mes=mes,
        ano=ano
    ).first()

    if fechamento_atual:
        return dinheiro(fechamento_atual.saldo_inicial)

    return obter_saldo_inicial_automatico(mes, ano)


def status_pago(valor):
    status = normalizar_texto(valor)

    return status in [
        "PAGO",
        "RECEBIDO",
        "OK",
        "QUITADO",
        "BAIXADO"
    ]


def status_cancelado(valor):
    status = normalizar_texto(valor)

    return status in [
        "CANCELADO",
        "CANCELADA"
    ]


def calcular_variacao_percentual(valor_atual, valor_anterior):
    valor_atual = dinheiro(valor_atual)
    valor_anterior = dinheiro(valor_anterior)

    if valor_anterior == 0:
        if valor_atual == 0:
            return 0

        return None

    return ((valor_atual - valor_anterior) / abs(valor_anterior)) * 100


# =========================================================
# CÁLCULO FINANCEIRO
# IMPORTADAS + LANÇAMENTOS MANUAIS
# =========================================================
def calcular_totais_financeiros(mes, ano, saldo_inicial=0):

    contas_pagar = ContaPagarImportada.query.filter_by(
        mes=mes,
        ano=ano
    ).all()

    contas_receber = ContaReceberImportada.query.filter_by(
        mes=mes,
        ano=ano
    ).all()

    lancamentos = LancamentoFinanceiro.query.filter_by(
        mes=mes,
        ano=ano
    ).all()

    total_entradas = 0
    total_saidas = 0
    total_a_pagar = 0
    total_a_receber = 0

    despesas_counter = Counter()
    despesas_assistencia_counter = Counter()
    despesas_logistica_counter = Counter()

    receitas_counter = Counter()
    clientes_counter = Counter()

    # =========================
    # CONTAS A PAGAR IMPORTADAS
    # =========================
    for c in contas_pagar:

        valor = dinheiro(c.valor)

        if c.pago:
            total_saidas += valor
        else:
            total_a_pagar += valor

        categoria = c.categoria or c.plano_contas or "SEM CATEGORIA"
        setor = c.setor or "ASSISTÊNCIA"

        despesas_counter[categoria] += valor

        if setor == "LOGÍSTICA":
            despesas_logistica_counter[categoria] += valor
        else:
            despesas_assistencia_counter[categoria] += valor

    # =========================
    # CONTAS A RECEBER IMPORTADAS
    # =========================
    for c in contas_receber:

        valor = dinheiro(c.total or c.valor)

        if c.pago:
            total_entradas += valor
        else:
            total_a_receber += valor

        categoria = c.categoria or c.plano_contas or "SEM CATEGORIA"
        cliente = c.cliente or "SEM CLIENTE"

        receitas_counter[categoria] += valor
        clientes_counter[cliente] += valor

    # =========================
    # LANÇAMENTOS MANUAIS
    # =========================
    for l in lancamentos:

        if status_cancelado(l.status):
            continue

        valor = dinheiro(l.valor)
        tipo = normalizar_texto(l.tipo)
        categoria = l.categoria or "SEM CATEGORIA"
        setor = l.setor or "GERAL"
        cliente = l.cliente or "SEM CLIENTE"

        if tipo == "RECEITA":

            if status_pago(l.status):
                total_entradas += valor
            else:
                total_a_receber += valor

            receitas_counter[categoria] += valor
            clientes_counter[cliente] += valor

        elif tipo == "DESPESA":

            if status_pago(l.status):
                total_saidas += valor
            else:
                total_a_pagar += valor

            despesas_counter[categoria] += valor

            if setor == "LOGÍSTICA":
                despesas_logistica_counter[categoria] += valor
            else:
                despesas_assistencia_counter[categoria] += valor

    lucro_mes = total_entradas - total_saidas
    saldo_final = dinheiro(saldo_inicial) + total_entradas - total_saidas

    margem_operacional = 0

    if total_entradas > 0:
        margem_operacional = (lucro_mes / total_entradas) * 100

    return {
        "total_entradas": total_entradas,
        "total_saidas": total_saidas,
        "total_a_pagar": total_a_pagar,
        "total_a_receber": total_a_receber,
        "lucro_mes": lucro_mes,
        "saldo_final": saldo_final,
        "margem_operacional": margem_operacional,

        # SEM LIMITE NO RANKING
        "ranking_despesas": despesas_counter.most_common(),
        "ranking_despesas_assistencia": despesas_assistencia_counter.most_common(),
        "ranking_despesas_logistica": despesas_logistica_counter.most_common(),
        "ranking_receitas": receitas_counter.most_common(),
        "ranking_clientes": clientes_counter.most_common(),
    }


# =========================================================
# EVOLUÇÃO FINANCEIRA MENSAL
# =========================================================
def calcular_evolucao_mensal(ano):
    labels = []
    entradas = []
    saidas = []
    lucros = []
    saldos_finais = []
    margens = []
    tabela = []

    nomes_meses = [
        "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
        "Jul", "Ago", "Set", "Out", "Nov", "Dez"
    ]

    for mes in range(1, 13):
        saldo_inicial = obter_saldo_inicial_mes(mes, ano)

        totais = calcular_totais_financeiros(
            mes=mes,
            ano=ano,
            saldo_inicial=saldo_inicial
        )

        total_entradas = dinheiro(totais["total_entradas"])
        total_saidas = dinheiro(totais["total_saidas"])
        lucro_mes = dinheiro(totais["lucro_mes"])
        saldo_final = dinheiro(totais["saldo_final"])
        margem_operacional = dinheiro(totais["margem_operacional"])

        labels.append(nomes_meses[mes - 1])
        entradas.append(round(total_entradas, 2))
        saidas.append(round(total_saidas, 2))
        lucros.append(round(lucro_mes, 2))
        saldos_finais.append(round(saldo_final, 2))
        margens.append(round(margem_operacional, 2))

        tabela.append({
            "mes": mes,
            "nome_mes": nomes_meses[mes - 1],
            "ano": ano,
            "saldo_inicial": round(dinheiro(saldo_inicial), 2),
            "entradas": round(total_entradas, 2),
            "saidas": round(total_saidas, 2),
            "lucro": round(lucro_mes, 2),
            "saldo_final": round(saldo_final, 2),
            "margem": round(margem_operacional, 2),
        })

    return {
        "labels": labels,
        "entradas": entradas,
        "saidas": saidas,
        "lucros": lucros,
        "saldos_finais": saldos_finais,
        "margens": margens,
        "tabela": tabela,
    }


def calcular_comparativo_mes_anterior(evolucao_mensal, mes):
    tabela = evolucao_mensal.get("tabela", [])

    if mes <= 1 or mes > 12:
        return None

    if len(tabela) < mes:
        return None

    atual = tabela[mes - 1]
    anterior = tabela[mes - 2]

    entradas_atual = dinheiro(atual["entradas"])
    entradas_anterior = dinheiro(anterior["entradas"])

    saidas_atual = dinheiro(atual["saidas"])
    saidas_anterior = dinheiro(anterior["saidas"])

    lucro_atual = dinheiro(atual["lucro"])
    lucro_anterior = dinheiro(anterior["lucro"])

    saldo_atual = dinheiro(atual["saldo_final"])
    saldo_anterior = dinheiro(anterior["saldo_final"])

    return {
        "mes_atual": atual["nome_mes"],
        "mes_anterior": anterior["nome_mes"],

        "entradas": {
            "atual": entradas_atual,
            "anterior": entradas_anterior,
            "diferenca": entradas_atual - entradas_anterior,
            "percentual": calcular_variacao_percentual(entradas_atual, entradas_anterior),
        },

        "saidas": {
            "atual": saidas_atual,
            "anterior": saidas_anterior,
            "diferenca": saidas_atual - saidas_anterior,
            "percentual": calcular_variacao_percentual(saidas_atual, saidas_anterior),
        },

        "lucro": {
            "atual": lucro_atual,
            "anterior": lucro_anterior,
            "diferenca": lucro_atual - lucro_anterior,
            "percentual": calcular_variacao_percentual(lucro_atual, lucro_anterior),
        },

        "saldo": {
            "atual": saldo_atual,
            "anterior": saldo_anterior,
            "diferenca": saldo_atual - saldo_anterior,
            "percentual": calcular_variacao_percentual(saldo_atual, saldo_anterior),
        },
    }


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

    fechamento = FechamentoMensal.query.filter_by(
        mes=mes,
        ano=ano
    ).first()

    saldo_inicial = obter_saldo_inicial_mes(mes, ano)

    totais = calcular_totais_financeiros(
        mes=mes,
        ano=ano,
        saldo_inicial=saldo_inicial
    )

    evolucao_mensal = calcular_evolucao_mensal(ano)
    comparativo_mes_anterior = calcular_comparativo_mes_anterior(evolucao_mensal, mes)

    return render_template(
        "gestao/dashboard.html",
        mes=mes,
        ano=ano,
        fechamento=fechamento,

        saldo_inicial=saldo_inicial,
        total_entradas=totais["total_entradas"],
        total_saidas=totais["total_saidas"],
        lucro_mes=totais["lucro_mes"],
        saldo_final=totais["saldo_final"],
        total_a_pagar=totais["total_a_pagar"],
        total_a_receber=totais["total_a_receber"],
        margem_operacional=totais["margem_operacional"],

        evolucao_mensal=evolucao_mensal,
        comparativo_mes_anterior=comparativo_mes_anterior,

        ranking_despesas=totais["ranking_despesas"],
        ranking_despesas_assistencia=totais["ranking_despesas_assistencia"],
        ranking_despesas_logistica=totais["ranking_despesas_logistica"],
        ranking_receitas=totais["ranking_receitas"],
        ranking_clientes=totais["ranking_clientes"]
    )


# =========================================================
# FECHAMENTO MENSAL
# =========================================================
@gestao_bp.route("/fechamento", methods=["GET", "POST"])
@gestao_required
def fechamento():

    hoje = datetime.now()

    mes = request.args.get("mes", type=int) or hoje.month
    ano = request.args.get("ano", type=int) or hoje.year

    fechamento_existente = FechamentoMensal.query.filter_by(
        mes=mes,
        ano=ano
    ).first()

    saldo_inicial = obter_saldo_inicial_mes(mes, ano)
    saldo_inicial_automatico = obter_saldo_inicial_automatico(mes, ano)

    if request.method == "POST":
        mes = request.form.get("mes", type=int)
        ano = request.form.get("ano", type=int)

        saldo_inicial = dinheiro(request.form.get("saldo_inicial"))

        totais = calcular_totais_financeiros(
            mes=mes,
            ano=ano,
            saldo_inicial=saldo_inicial
        )

        fechamento_existente = FechamentoMensal.query.filter_by(
            mes=mes,
            ano=ano
        ).first()

        if fechamento_existente:
            fechamento_existente.saldo_inicial = saldo_inicial
            fechamento_existente.total_entradas = totais["total_entradas"]
            fechamento_existente.total_saidas = totais["total_saidas"]
            fechamento_existente.lucro_mes = totais["lucro_mes"]
            fechamento_existente.saldo_final = totais["saldo_final"]
            fechamento_existente.total_a_pagar = totais["total_a_pagar"]
            fechamento_existente.total_a_receber = totais["total_a_receber"]
            fechamento_existente.margem_operacional = totais["margem_operacional"]
            fechamento_existente.fechado = True
        else:
            fechamento_existente = FechamentoMensal(
                mes=mes,
                ano=ano,
                saldo_inicial=saldo_inicial,
                total_entradas=totais["total_entradas"],
                total_saidas=totais["total_saidas"],
                lucro_mes=totais["lucro_mes"],
                saldo_final=totais["saldo_final"],
                total_a_pagar=totais["total_a_pagar"],
                total_a_receber=totais["total_a_receber"],
                margem_operacional=totais["margem_operacional"],
                fechado=True
            )

            db.session.add(fechamento_existente)

        db.session.commit()

        flash("Fechamento mensal salvo com sucesso!", "success")
        return redirect(f"/gestao/fechamento?mes={mes}&ano={ano}")

    totais = calcular_totais_financeiros(
        mes=mes,
        ano=ano,
        saldo_inicial=saldo_inicial
    )

    return render_template(
        "gestao/fechamento.html",
        mes=mes,
        ano=ano,
        fechamento=fechamento_existente,
        saldo_inicial=saldo_inicial,
        saldo_inicial_automatico=saldo_inicial_automatico,
        total_entradas=totais["total_entradas"],
        total_saidas=totais["total_saidas"],
        lucro_mes=totais["lucro_mes"],
        saldo_final=totais["saldo_final"],
        total_a_pagar=totais["total_a_pagar"],
        total_a_receber=totais["total_a_receber"],
        margem_operacional=totais["margem_operacional"]
    )


# =========================================================
# LANÇAMENTOS MANUAIS
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


@gestao_bp.route("/lancamentos/excluir/<int:id>")
@gestao_required
def excluir_lancamento(id):

    lancamento = LancamentoFinanceiro.query.get_or_404(id)

    db.session.delete(lancamento)
    db.session.commit()

    flash("Lançamento excluído com sucesso!", "success")
    return redirect("/gestao/lancamentos")