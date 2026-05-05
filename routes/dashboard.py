from flask import Blueprint, render_template, request, redirect, session
from models.manutencao import Manutencao
from collections import defaultdict, Counter
from datetime import datetime

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/")
def dashboard():

    if not session.get("user_id"):
        return redirect("/login")

    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")

    query = Manutencao.query

    if data_inicio and data_fim:
        try:
            inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
            fim = datetime.strptime(data_fim, "%Y-%m-%d")
            query = query.filter(Manutencao.data.between(inicio, fim))
        except:
            pass

    registros = query.all()

    def formatar_frota(valor):
        try:
            return str(int(float(valor)))
        except:
            return "Sem frota"

    por_mes = defaultdict(int)
    tipos_counter = Counter()
    frotas_counter = Counter()
    atendimento_counter = Counter()
    dados_frotas = defaultdict(lambda: defaultdict(int))

    for r in registros:
        if r.data:
            mes = r.data.strftime("%Y-%m")
            por_mes[mes] += 1
        else:
            continue

        tipo = (r.tipo_manutencao or "Sem tipo")
        frota = formatar_frota(r.numero_frota)
        atendimento = (r.tipo_atendimento or "Sem info")

        tipos_counter[tipo] += 1
        frotas_counter[frota] += 1
        atendimento_counter[atendimento] += 1

        dados_frotas[frota][mes] += 1

    # 🔥 MENSAL
    labels = sorted(por_mes.keys())
    valores = [por_mes[m] for m in labels]

    # 🔥 TIPOS
    tipos = tipos_counter.most_common()
    labels_tipo = [t[0] for t in tipos]
    valores_tipo = [t[1] for t in tipos]

    # 🔥 PARETO
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

    # 🔥 ATENDIMENTO
    labels_atendimento = list(atendimento_counter.keys())
    valores_atendimento = list(atendimento_counter.values())

    # 🔥 INSIGHT
    insight = ""
    if frotas:
        topo = frotas[0]
        insight = f"A frota {topo[0]} concentra maior volume ({topo[1]} manutenções)"

    # 🔥 KPIs
    total = len(registros)

    frotas_counter_kpi = Counter(
        formatar_frota(r.numero_frota) for r in registros
    )

    corretivas = 0
    preventivas = 0

    for r in registros:
        frota = formatar_frota(r.numero_frota)

        if frotas_counter_kpi[frota] >= 3:
            corretivas += 1
        else:
            preventivas += 1

    andamento = sum(
        1 for r in registros
        if "andamento" in (r.status or "").lower()
    )

    return render_template(
        "dashboard.html",

        total=total,
        corretivas=corretivas,
        preventivas=preventivas,
        andamento=andamento,

        labels=labels,
        valores=valores,
        labels_tipo=labels_tipo,
        valores_tipo=valores_tipo,
        labels_frota=labels_frota,
        valores_frota=valores_frota,
        pareto_percentual=pareto_percentual,
        labels_atendimento=labels_atendimento,
        valores_atendimento=valores_atendimento,
        insight=insight
    )