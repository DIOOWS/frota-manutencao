from flask import Blueprint, render_template, request, redirect, session
from models.manutencao import Manutencao
from collections import defaultdict, Counter
from datetime import datetime

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def dashboard():

    # 🔐 LOGIN
    if not session.get("user_id"):
        return redirect("/login")

    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")
    mes_filtro = request.args.get("mes")

    query = Manutencao.query

    inicio_mes_filtro = None

    # =========================
    # 🔥 FILTRO POR MÊS
    # =========================
    if mes_filtro:

        try:

            inicio_mes_filtro = datetime.strptime(
                mes_filtro + "-01",
                "%Y-%m-%d"
            )

            if inicio_mes_filtro.month == 12:

                fim = inicio_mes_filtro.replace(
                    year=inicio_mes_filtro.year + 1,
                    month=1
                )

            else:

                fim = inicio_mes_filtro.replace(
                    month=inicio_mes_filtro.month + 1
                )

            query = query.filter(
                Manutencao.data >= inicio_mes_filtro,
                Manutencao.data < fim
            )

        except:
            pass

    # =========================
    # 🔥 FILTRO POR DATA
    # =========================
    elif data_inicio and data_fim:

        try:

            inicio = datetime.strptime(
                data_inicio,
                "%Y-%m-%d"
            )

            fim = datetime.strptime(
                data_fim,
                "%Y-%m-%d"
            )

            query = query.filter(
                Manutencao.data.between(inicio, fim)
            )

        except:
            pass

    registros = query.all()

    # =========================
    # 🔥 HELPERS
    # =========================
    def formatar_frota(valor):

        try:
            return str(int(float(valor)))
        except:
            return "Sem frota"

    # =========================
    # 🔥 ESTRUTURAS
    # =========================
    por_mes = defaultdict(int)

    por_mes_corretiva = defaultdict(int)
    por_mes_preventiva = defaultdict(int)

    atendimento_counter = Counter()
    servicos_counter = Counter()
    causas_counter = Counter()

    # =========================
    # 🔥 LOOP PRINCIPAL
    # =========================
    for r in registros:

        # 🔥 MÊS
        if r.data:

            mes = r.data.strftime("%m-%Y")

            por_mes[mes] += 1

        else:
            continue

        # 🔥 ATENDIMENTO
        atendimento = (
            r.tipo_atendimento or "SEM INFO"
        )

        atendimento_counter[atendimento] += 1

        # 🔥 SERVIÇO
        tipo_servico = (
            r.tipo_servico or ""
        ).upper().strip()

        if tipo_servico == "CORRETIVA":

            por_mes_corretiva[mes] += 1

            servicos_counter["CORRETIVA"] += 1

        elif tipo_servico == "PREVENTIVA":

            por_mes_preventiva[mes] += 1

            servicos_counter["PREVENTIVA"] += 1

        # 🔥 CAUSAS
        causa = (
            (r.causa or "")
            .strip()
            .upper()
        )

        if causa in ["", "-", "NONE"]:
            causa = "SEM CAUSA"

        causas_counter[causa] += 1

    # =========================
    # 🔥 KPIs
    # =========================
    total = len(registros)

    corretivas = servicos_counter.get(
        "CORRETIVA",
        0
    )

    preventivas = servicos_counter.get(
        "PREVENTIVA",
        0
    )

    andamento = sum(
        1 for r in registros
        if "ANDAMENTO" in (r.status or "").upper()
    )

    # =========================
    # 🔥 ÚLTIMAS FINALIZAÇÕES
    # =========================
    ultimas_finalizacoes = [

        r for r in registros

        if "FINALIZADO" in (
            r.status or ""
        ).upper()

        and r.data_saida
    ]

    ultimas_finalizacoes = sorted(

        ultimas_finalizacoes,

        key=lambda r: (
            r.data_saida,
            r.id
        ),

        reverse=True

    )[:5]

    # =========================
    # 🔥 GRÁFICO MENSAL
    # =========================
    if mes_filtro and inicio_mes_filtro:

        labels = [
            inicio_mes_filtro.strftime("%m-%Y")
        ]

        valores = [total]

        valores_corretiva_mes = [
            corretivas
        ]

        valores_preventiva_mes = [
            preventivas
        ]

    else:

        labels = sorted(

            por_mes.keys(),

            key=lambda x: datetime.strptime(
                x,
                "%m-%Y"
            )
        )

        valores = [
            por_mes[m]
            for m in labels
        ]

        valores_corretiva_mes = [
            por_mes_corretiva[m]
            for m in labels
        ]

        valores_preventiva_mes = [
            por_mes_preventiva[m]
            for m in labels
        ]

    # =========================
    # 🔥 FUNIL DE CAUSAS
    # =========================
    causas = sorted(

        causas_counter.items(),

        key=lambda x: x[1],

        reverse=True

    )[:10]

    labels_frota = [
        c[0]
        for c in causas
    ]

    valores_frota = [
        c[1]
        for c in causas
    ]

    # =========================
    # 🔥 ATENDIMENTO
    # =========================
    labels_atendimento = list(
        atendimento_counter.keys()
    )

    valores_atendimento = list(
        atendimento_counter.values()
    )

    # =========================
    # 🔥 CORRETIVA vs PREVENTIVA
    # =========================
    dados_corretiva = {

        "labels": [
            "Corretiva",
            "Preventiva"
        ],

        "valores": [
            corretivas,
            preventivas
        ]
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

        labels_atendimento=labels_atendimento,
        valores_atendimento=valores_atendimento,

        dados_corretiva=dados_corretiva,

        valores_corretiva_mes=valores_corretiva_mes,
        valores_preventiva_mes=valores_preventiva_mes,

        ultimas_finalizacoes=ultimas_finalizacoes,
    )