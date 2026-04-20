from flask import Blueprint, render_template, request, redirect, session
from models.manutencao import Manutencao
from collections import defaultdict, Counter

dashboard_bp = Blueprint("dashboard", __name__)


# 🔥 LOGIN
@dashboard_bp.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":
        user = request.form.get("usuario")
        senha = request.form.get("senha")

        # 🔥 LOGIN SIMPLES PRA DEMO
        if user == "admin" and senha == "123":
            session["logado"] = True
            return redirect("/")

    return render_template("login.html")


# 🔥 LOGOUT
@dashboard_bp.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# 🔥 DASHBOARD
@dashboard_bp.route("/")
def dashboard():

    # 🔥 PROTEÇÃO
    if not session.get("logado"):
        return redirect("/login")

    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")

    query = Manutencao.query

    if data_inicio and data_fim:
        query = query.filter(
            Manutencao.data.between(data_inicio, data_fim)
        )

    registros = query.all()

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

    labels = sorted(por_mes.keys())
    valores = [por_mes[m] for m in labels]

    tipos_ordenados = tipos_counter.most_common()
    labels_tipo = [t[0] for t in tipos_ordenados]
    valores_tipo = [t[1] for t in tipos_ordenados]

    # 🔥 PARETO (TODAS AS FROTAS)
    frotas_ordenadas = sorted(
        frotas_counter.items(),
        key=lambda x: x[1],
        reverse=True
    )

    labels_frota = [f[0] for f in frotas_ordenadas]
    valores_frota = [f[1] for f in frotas_ordenadas]

    total_manutencoes = sum(valores_frota) or 1

    pareto_percentual = []
    acumulado = 0

    for valor in valores_frota:
        perc = (valor / total_manutencoes) * 100
        acumulado += perc
        pareto_percentual.append(round(acumulado, 2))

    # 🔥 FROTAS CRÍTICAS
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

    labels_atendimento = list(atendimento_counter.keys())
    valores_atendimento = list(atendimento_counter.values())

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
        labels_atendimento=labels_atendimento,
        valores_atendimento=valores_atendimento,
        dados_frotas=dados_frotas,
        frotas_criticas=frotas_criticas,
        dados_tipos_detalhe=dados_tipos_detalhe,
    )