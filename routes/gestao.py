from flask import Blueprint, render_template, request, redirect, flash
from utils.auth import gestao_required
from models.lancamento_financeiro import LancamentoFinanceiro
from models.fechamento_mensal import FechamentoMensal
from models.conta_pagar_importada import ContaPagarImportada
from models.conta_receber_importada import ContaReceberImportada
from database import db
from datetime import datetime
from collections import Counter
import calendar


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


# =========================================================
# INTELIGÊNCIA FINANCEIRA / TOMADA DE DECISÃO
# =========================================================
def calcular_inteligencia_financeira(totais, evolucao_mensal, mes, ano, saldo_inicial):
    total_entradas = dinheiro(totais["total_entradas"])
    total_saidas = dinheiro(totais["total_saidas"])
    total_a_pagar = dinheiro(totais["total_a_pagar"])
    total_a_receber = dinheiro(totais["total_a_receber"])
    lucro_mes = dinheiro(totais["lucro_mes"])
    saldo_final = dinheiro(totais["saldo_final"])
    margem = dinheiro(totais["margem_operacional"])

    percentual_saidas = 0
    if total_entradas > 0:
        percentual_saidas = (total_saidas / total_entradas) * 100

    saldo_projetado_pos_obrigacoes = saldo_final + total_a_receber - total_a_pagar

    faltante_equilibrio = 0
    sobra_equilibrio = 0

    if total_saidas > total_entradas:
        faltante_equilibrio = total_saidas - total_entradas
    else:
        sobra_equilibrio = total_entradas - total_saidas

    despesas_top = totais["ranking_despesas"][:5]
    despesas_top3 = totais["ranking_despesas"][:3]

    total_top3 = sum(dinheiro(valor) for _, valor in despesas_top3)
    economia_10_top3 = total_top3 * 0.10

    maior_despesa_nome = None
    maior_despesa_valor = 0
    maior_despesa_percentual = 0

    if despesas_top:
        maior_despesa_nome = despesas_top[0][0]
        maior_despesa_valor = dinheiro(despesas_top[0][1])

        if total_saidas > 0:
            maior_despesa_percentual = (maior_despesa_valor / total_saidas) * 100

    meses_com_movimento = [
        item for item in evolucao_mensal["tabela"]
        if dinheiro(item["entradas"]) != 0 or dinheiro(item["saidas"]) != 0
    ]

    meses_positivos = [
        item for item in meses_com_movimento
        if dinheiro(item["lucro"]) > 0
    ]

    meses_negativos = [
        item for item in meses_com_movimento
        if dinheiro(item["lucro"]) < 0
    ]

    melhor_mes = None
    pior_mes = None
    media_resultado = 0

    if meses_com_movimento:
        melhor_mes = max(meses_com_movimento, key=lambda item: dinheiro(item["lucro"]))
        pior_mes = min(meses_com_movimento, key=lambda item: dinheiro(item["lucro"]))
        media_resultado = sum(dinheiro(item["lucro"]) for item in meses_com_movimento) / len(meses_com_movimento)

    hoje = datetime.now()
    projecao = None

    if hoje.month == mes and hoje.year == ano and hoje.day > 0:
        dias_no_mes = calendar.monthrange(ano, mes)[1]

        entradas_projetadas = (total_entradas / hoje.day) * dias_no_mes
        saidas_projetadas = (total_saidas / hoje.day) * dias_no_mes
        resultado_projetado = entradas_projetadas - saidas_projetadas

        projecao = {
            "dia_atual": hoje.day,
            "dias_no_mes": dias_no_mes,
            "entradas_projetadas": entradas_projetadas,
            "saidas_projetadas": saidas_projetadas,
            "resultado_projetado": resultado_projetado,
        }

    nivel = "success"
    titulo_situacao = "Operação saudável"
    resumo_situacao = "O mês apresenta resultado positivo e margem operacional favorável."

    if lucro_mes < 0:
        nivel = "danger"
        titulo_situacao = "Resultado negativo"
        resumo_situacao = "As saídas superaram as entradas. O foco imediato deve ser reduzir custos e acelerar recebimentos."
    elif margem < 10:
        nivel = "warning"
        titulo_situacao = "Margem apertada"
        resumo_situacao = "O mês está positivo, mas com margem baixa. Qualquer aumento de custo pode comprometer o resultado."
    elif percentual_saidas >= 80:
        nivel = "warning"
        titulo_situacao = "Despesas pressionando"
        resumo_situacao = "As saídas estão consumindo uma parte alta das entradas. Vale revisar os maiores custos."
    elif saldo_projetado_pos_obrigacoes < 0:
        nivel = "danger"
        titulo_situacao = "Risco de caixa"
        resumo_situacao = "Mesmo com o saldo atual, as obrigações em aberto podem deixar o caixa negativo."

    alertas = []

    if total_entradas == 0 and total_saidas == 0:
        alertas.append({
            "nivel": "warning",
            "titulo": "Sem movimento financeiro",
            "descricao": "Não há entradas nem saídas registradas para o mês filtrado.",
            "acao": "Verifique se as importações e lançamentos deste mês foram feitos corretamente."
        })

    if lucro_mes < 0:
        alertas.append({
            "nivel": "danger",
            "titulo": "Prejuízo no mês",
            "descricao": "O mês está fechando com mais saídas do que entradas.",
            "acao": "Ataque as maiores despesas e priorize recebimentos em aberto."
        })

    if percentual_saidas >= 80 and total_entradas > 0:
        alertas.append({
            "nivel": "warning",
            "titulo": "Custo consumindo receita",
            "descricao": f"As saídas representam {percentual_saidas:.2f}% das entradas.",
            "acao": "Busque reduzir custos variáveis ou renegociar os maiores pagamentos."
        })

    if total_a_pagar > saldo_final:
        alertas.append({
            "nivel": "danger",
            "titulo": "A pagar maior que saldo final",
            "descricao": "As obrigações em aberto são maiores que o saldo final atual.",
            "acao": "Priorize recebimentos e evite novos compromissos antes de reforçar o caixa."
        })

    if total_a_receber > total_entradas and total_a_receber > 0:
        alertas.append({
            "nivel": "warning",
            "titulo": "Recebíveis importantes em aberto",
            "descricao": "O valor a receber é maior que o que já entrou no mês.",
            "acao": "Acompanhe cobranças e antecipe recebimentos quando possível."
        })

    if maior_despesa_nome:
        alertas.append({
            "nivel": "info",
            "titulo": "Maior impacto de despesa",
            "descricao": f"{maior_despesa_nome} representa R$ {maior_despesa_valor:,.2f} no mês.",
            "acao": "Analise se esse custo pode ser reduzido, renegociado ou controlado por limite."
        })

    if not alertas:
        alertas.append({
            "nivel": "success",
            "titulo": "Sem alertas críticos",
            "descricao": "Os principais indicadores do mês estão dentro de um cenário saudável.",
            "acao": "Mantenha o acompanhamento e preserve a margem operacional."
        })

    acoes_recomendadas = []

    if lucro_mes < 0:
        acoes_recomendadas.append("Reduzir imediatamente as 3 maiores despesas do mês.")
        acoes_recomendadas.append("Priorizar cobrança dos valores em aberto.")
        acoes_recomendadas.append("Revisar se alguma despesa pontual distorceu o mês.")

    if economia_10_top3 > 0:
        acoes_recomendadas.append(
            f"Reduzir 10% nas 3 maiores despesas aumentaria o resultado em aproximadamente R$ {economia_10_top3:,.2f}."
        )

    if total_a_receber > 0:
        acoes_recomendadas.append(
            f"Receber os valores em aberto pode reforçar o caixa em R$ {total_a_receber:,.2f}."
        )

    if total_a_pagar > 0:
        acoes_recomendadas.append(
            f"Planejar os pagamentos em aberto de R$ {total_a_pagar:,.2f} para não pressionar o caixa."
        )

    if not acoes_recomendadas:
        acoes_recomendadas.append("Manter controle do orçamento e acompanhar os maiores custos semanalmente.")

    return {
        "nivel": nivel,
        "titulo_situacao": titulo_situacao,
        "resumo_situacao": resumo_situacao,
        "percentual_saidas": percentual_saidas,
        "saldo_projetado_pos_obrigacoes": saldo_projetado_pos_obrigacoes,
        "faltante_equilibrio": faltante_equilibrio,
        "sobra_equilibrio": sobra_equilibrio,
        "despesas_top": despesas_top,
        "despesas_top3": despesas_top3,
        "total_top3": total_top3,
        "economia_10_top3": economia_10_top3,
        "maior_despesa_nome": maior_despesa_nome,
        "maior_despesa_valor": maior_despesa_valor,
        "maior_despesa_percentual": maior_despesa_percentual,
        "meses_com_movimento": len(meses_com_movimento),
        "meses_positivos": len(meses_positivos),
        "meses_negativos": len(meses_negativos),
        "melhor_mes": melhor_mes,
        "pior_mes": pior_mes,
        "media_resultado": media_resultado,
        "projecao": projecao,
        "alertas": alertas,
        "acoes_recomendadas": acoes_recomendadas,
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

    inteligencia_financeira = calcular_inteligencia_financeira(
        totais=totais,
        evolucao_mensal=evolucao_mensal,
        mes=mes,
        ano=ano,
        saldo_inicial=saldo_inicial
    )

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
        inteligencia_financeira=inteligencia_financeira,

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