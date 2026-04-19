from flask import Blueprint, render_template, request
from models.manutencao import Manutencao
from collections import defaultdict, Counter

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/")
def dashboard():

    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")

    query = Manutencao.query

    if data_inicio and data_fim:
        query = query.filter(
            Manutencao.data.between(data_inicio, data_fim)
        )

    registros = query.all()

    # 🔥 função para padronizar frota
    def formatar_frota(valor):
        try:
            return str(int(float(valor)))
        except:
            return "Sem frota"

    # 🔥 gráfico por mês
    por_mes = defaultdict(int)
    for r in registros:
        if r.data:
            mes = r.data.strftime("%Y-%m")
            por_mes[mes] += 1

    labels = sorted(por_mes.keys())
    valores = [por_mes[m] for m in labels]

    total = len(registros)

    # 🔥 tipo de serviço
    corretivas = sum(
        1 for r in registros
        if (r.tipo_servico or "").strip().lower() == "corretiva"
    )

    preventivas = sum(
        1 for r in registros
        if (r.tipo_servico or "").strip().lower() == "preventiva"
    )

    # 🔥 status
    andamento = sum(
        1 for r in registros
        if (r.status or "").strip().lower() == "andamento"
    )

    concluidas = sum(
        1 for r in registros
        if (r.status or "").strip().lower() == "finalizado"
    )

    # 🔥 tipos de manutenção
    tipos = Counter([
        (r.tipo_manutencao or "Sem tipo")
        for r in registros
    ])

    labels_tipo = list(tipos.keys())
    valores_tipo = list(tipos.values())

    # 🔥 TOP FROTAS
    frotas = Counter([
        formatar_frota(r.numero_frota)
        for r in registros
    ])

    top_frotas = frotas.most_common(5)

    labels_frota = [f[0] for f in top_frotas]
    valores_frota = [f[1] for f in top_frotas]

    # 🔥 INTERNO vs EXTERNO
    atendimento = Counter([
        (r.tipo_atendimento or "Sem info").strip().lower()
        for r in registros
    ])

    labels_atendimento = list(atendimento.keys())
    valores_atendimento = list(atendimento.values())

    # 🔥 HISTÓRICO POR FROTA
    dados_frotas = {}

    for r in registros:
        if r.numero_frota and r.data:

            frota = formatar_frota(r.numero_frota)

            if frota not in dados_frotas:
                dados_frotas[frota] = defaultdict(int)

            mes = r.data.strftime("%Y-%m")
            dados_frotas[frota][mes] += 1

    # ordenar meses
    dados_frotas = {
        frota: dict(sorted(meses.items()))
        for frota, meses in dados_frotas.items()
    }

    # 🔥 FROTAS CRÍTICAS
    limite = 3

    frotas_criticas = [
        (frota, qtd)
        for frota, qtd in frotas.items()
        if qtd >= limite
    ]

    frotas_criticas = sorted(
        frotas_criticas,
        key=lambda x: x[1],
        reverse=True
    )[:5]

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
        labels_atendimento=labels_atendimento,
        valores_atendimento=valores_atendimento,
        dados_frotas=dados_frotas,
        frotas_criticas=frotas_criticas,
    )