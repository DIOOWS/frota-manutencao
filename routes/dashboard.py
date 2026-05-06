from flask import Blueprint, render_template, request, redirect, session
from models.manutencao import Manutencao
from collections import defaultdict, Counter
from datetime import datetime

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def dashboard():

    # 🔐 PROTEÇÃO LOGIN
    if not session.get("user_id"):
        return redirect("/login")

    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")
    mes_filtro = request.args.get("mes")

    query = Manutencao.query

    inicio_mes_filtro = None

    # 🔥 PRIORIDADE: FILTRO POR MÊS
    if mes_filtro:
        try:
            inicio_mes_filtro = datetime.strptime(mes_filtro + "-01", "%Y-%m-%d")

            if inicio_mes_filtro.month == 12:
                fim = inicio_mes_filtro.replace(year=inicio_mes_filtro.year + 1, month=1)
            else:
                fim = inicio_mes_filtro.replace(month=inicio_mes_filtro.month + 1)

            query = query.filter(
                Manutencao.data >= inicio_mes_filtro,
                Manutencao.data < fim
            )
        except:
            pass

    # 🔥 SENÃO, USA FILTRO POR DATA
    elif data_inicio and data_fim:
        try:
            inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
            fim = datetime.strptime(data_fim, "%Y-%m-%d")
            query = query.filter(Manutencao.data.between(inicio, fim))
        except:
            pass

    registros = query.all()

    # 🔧 FORMATA FROTA
    def formatar_frota(valor):
        try:
            return str(int(float(valor)))
        except:
            return "Sem frota"

    # 🔥 ESTRUTURAS
    por_mes = defaultdict(int)
    por_mes_corretiva = defaultdict(int)
    por_mes_preventiva = defaultdict(int)

    frotas_counter = Counter()
    atendimento_counter = Counter()
    servicos_counter = Counter()

    # 🔥 LOOP PRINCIPAL
    for r in registros:

        if r.data:
            # 🔥 APARECE NO GRÁFICO COMO MÊS-ANO
            mes = r.data.strftime("%m-%Y")
            por_mes[mes] += 1
        else:
            continue

        # FROTA
        frota = formatar_frota(r.numero_frota)
        frotas_counter[frota] += 1

        # ATENDIMENTO
        atendimento = (r.tipo_atendimento or "Sem info")
        atendimento_counter[atendimento] += 1

        # CORRETIVA / PREVENTIVA
        tipo_servico = (r.tipo_servico or "").upper().strip()

        if tipo_servico == "CORRETIVA":
            por_mes_corretiva[mes] += 1
            servicos_counter["CORRETIVA"] += 1

        elif tipo_servico == "PREVENTIVA":
            por_mes_preventiva[mes] += 1
            servicos_counter["PREVENTIVA"] += 1

    # =========================
    # 🔥 KPIs
    # =========================
    total = len(registros)

    corretivas = servicos_counter.get("CORRETIVA", 0)
    preventivas = servicos_counter.get("PREVENTIVA", 0)

    andamento = sum(
        1 for r in registros
        if "andamento" in (r.status or "").lower()
    )

    # =========================
    # 🔥 MENSAL CORRETO
    # =========================
    if mes_filtro and inicio_mes_filtro:
        labels = [inicio_mes_filtro.strftime("%m-%Y")]
        valores = [total]
        valores_corretiva_mes = [corretivas]
        valores_preventiva_mes = [preventivas]
    else:
        labels = sorted(
            por_mes.keys(),
            key=lambda x: datetime.strptime(x, "%m-%Y")
        )
        valores = [por_mes[m] for m in labels]
        valores_corretiva_mes = [por_mes_corretiva[m] for m in labels]
        valores_preventiva_mes = [por_mes_preventiva[m] for m in labels]

    # =========================
    # 🔥 PARETO
    # =========================
    frotas = sorted(frotas_counter.items(), key=lambda x: x[1], reverse=True)[:10]
    total_geral = sum(frotas_counter.values()) or 1

    labels_frota = [f[0] for f in frotas]
    valores_frota = [f[1] for f in frotas]

    acumulado = 0
    pareto_percentual = []

    for v in valores_frota:
        perc = (v / total_geral) * 100
        acumulado += perc
        pareto_percentual.append(round(acumulado, 2))

    # =========================
    # 🔥 ATENDIMENTO (PIZZA)
    # =========================
    labels_atendimento = list(atendimento_counter.keys())
    valores_atendimento = list(atendimento_counter.values())

    # =========================
    # 🔥 CORRETIVA vs PREVENTIVA
    # =========================
    dados_corretiva = {
        "labels": ["Corretiva", "Preventiva"],
        "valores": [corretivas, preventivas]
    }

    # =========================
    # 🔥 RENDER
    # =========================
    return render_template(
        "dashboard.html",

        total=total,
        corretivas=corretivas,
        preventivas=preventivas,
        andamento=andamento,

        labels=labels,
        valores=valores,

        labels_frota=labels_frota,
        valores_frota=valores_frota,
        pareto_percentual=pareto_percentual,

        labels_atendimento=labels_atendimento,
        valores_atendimento=valores_atendimento,

        dados_corretiva=dados_corretiva,

        valores_corretiva_mes=valores_corretiva_mes,
        valores_preventiva_mes=valores_preventiva_mes,
    )