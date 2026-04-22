from flask import Blueprint, render_template, request, redirect, session
from models.manutencao import Manutencao
from collections import defaultdict, Counter
from datetime import datetime

dashboard_bp = Blueprint("dashboard", __name__)


# 🔥 DASHBOARD
@dashboard_bp.route("/")
def dashboard():

    # 🔐 PROTEÇÃO CORRETA
    if not session.get("user_id"):
        return redirect("/login")

    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")

    query = Manutencao.query

    # 🔥 FILTRO DE DATA
    if data_inicio and data_fim:
        try:
            inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
            fim = datetime.strptime(data_fim, "%Y-%m-%d")

            query = query.filter(
                Manutencao.data.between(inicio, fim)
            )
        except:
            pass

    # 🔥 ORDENAÇÃO
    registros = query.order_by(Manutencao.id.desc()).all()

    def formatar_frota(valor):
        try:
            return str(int(float(valor)))
        except:
            return "Sem frota"

    total = len(registros)

    por_mes = defaultdict(int)
    tipos_counter = Counter()
    frotas_counter = Counter()
    atendimento_counter = Counter()
    dados_frotas = {}
    dados_tipos_detalhe = {}

    corretivas = 0
    preventivas = 0
    andamento = 0
    concluidas = 0

    for r in registros:

        if r.data:
            mes = r.data.strftime("%Y-%m")
            por_mes[mes] += 1

        tipo = (r.tipo_manutencao or "Sem tipo").strip().upper()
        tipo_servico = (r.tipo_servico or "").strip().lower()
        status = (r.status or "").strip().lower()
        atendimento = (r.tipo_atendimento or "Sem info").strip().lower()
        frota = formatar_frota(r.numero_frota)

        tipos_counter[tipo] += 1
        frotas_counter[frota] += 1
        atendimento_counter[atendimento] += 1

        if tipo_servico == "corretiva":
            corretivas += 1
        elif tipo_servico == "preventiva":
            preventivas += 1

        if status == "andamento":
            andamento += 1
        elif status == "finalizado":
            concluidas += 1

        if r.numero_frota and r.data:
            if frota not in dados_frotas:
                dados_frotas[frota] = defaultdict(int)

            dados_frotas[frota][mes] += 1

        if tipo not in dados_tipos_detalhe:
            dados_tipos_detalhe[tipo] = []

        dados_tipos_detalhe[tipo].append({
            "frota": frota,
            "data": r.data.strftime("%d/%m") if r.data else "Sem data"
        })

    # =========================
    # 🔥 GRÁFICO POR MÊS
    # =========================
    labels = sorted(por_mes.keys())
    valores = [por_mes[m] for m in labels]

    # =========================
    # 🔥 TIPOS
    # =========================
    tipos_ordenados = tipos_counter.most_common()
    labels_tipo = [t[0] for t in tipos_ordenados]
    valores_tipo = [t[1] for t in tipos_ordenados]

    # =========================
    # 🔥 PARETO
    # =========================
    total_manutencoes = sum(frotas_counter.values()) or 1

    frotas_ordenadas = sorted(
        frotas_counter.items(),
        key=lambda x: x[1],
        reverse=True
    )

    top_n = 10
    top = frotas_ordenadas[:top_n]
    outros = frotas_ordenadas[top_n:]

    soma_outros = sum(v for _, v in outros)

    if soma_outros > 0:
        top.append(("Outros", soma_outros))

    labels_frota = [f[0] for f in top]
    valores_frota = [f[1] for f in top]

    pareto_percentual = []
    acumulado = 0

    for i, valor in enumerate(valores_frota):

        if labels_frota[i] == "Outros":
            pareto_percentual.append(
                pareto_percentual[-1] if pareto_percentual else 0
            )
            continue

        perc = (valor / total_manutencoes) * 100
        acumulado += perc
        pareto_percentual.append(round(acumulado, 2))

    pareto_corte_80 = 0

    for i, v in enumerate(pareto_percentual):
        if v >= 80:
            pareto_corte_80 = i
            break

    # =========================
    # 🔥 FROTAS CRÍTICAS
    # =========================
    limite = 3

    frotas_criticas = [
        (frota, qtd)
        for frota, qtd in frotas_counter.items()
        if qtd >= limite
    ]

    frotas_criticas = sorted(
        frotas_criticas,
        key=lambda x: x[1],
        reverse=True
    )[:5]

    # =========================
    # 🔥 ATENDIMENTO
    # =========================
    labels_atendimento = list(atendimento_counter.keys())
    valores_atendimento = list(atendimento_counter.values())

    # =========================
    # 🔥 RENDER
    # =========================
    return render_template(
        "dashboard.html",
        total=total,
        corretivas=corretivas,
        preventivas=preventivas,
        andamento=andamento,
        concluidas=concluidas,
        labels=labels,
        valores=valores,
        labels_tipo=labels_tipo,
        valores_tipo=valores_tipo,
        labels_frota=labels_frota,
        valores_frota=valores_frota,
        pareto_percentual=pareto_percentual,
        pareto_corte_80=pareto_corte_80,
        labels_atendimento=labels_atendimento,
        valores_atendimento=valores_atendimento,
        dados_frotas=dados_frotas,
        frotas_criticas=frotas_criticas,
        dados_tipos_detalhe=dados_tipos_detalhe,
    )