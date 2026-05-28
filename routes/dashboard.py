from flask import Blueprint, render_template, request, redirect, session
from models.manutencao import Manutencao
from models.usuario import Usuario
from database import db
from collections import defaultdict, Counter
from datetime import datetime

dashboard_bp = Blueprint("dashboard", __name__)


def usuario_eh_admin_ou_gestao():
    return session.get("user_role") in ["admin", "gestao", "gestor"]


def normalizar_texto(valor):
    if valor is None:
        return None

    valor = str(valor).strip()

    if not valor:
        return None

    return " ".join(valor.split()).upper()


def usuario_logado():
    user_id = session.get("user_id")

    if not user_id:
        return None

    return Usuario.query.get(user_id)


def nome_cliente_usuario_logado():
    usuario = usuario_logado()

    if not usuario:
        return None

    if usuario.cliente:
        return normalizar_texto(usuario.cliente.nome)

    return None


def aplicar_filtro_cliente(query):
    if usuario_eh_admin_ou_gestao():
        return query

    cliente_nome = nome_cliente_usuario_logado()

    if not cliente_nome:
        return query.filter(Manutencao.id == 0)

    return query.filter(
        db.func.upper(Manutencao.cliente) == cliente_nome.upper()
    )


@dashboard_bp.route("/")
def dashboard():

    if not session.get("user_id"):
        return redirect("/login")

    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")
    mes_filtro = request.args.get("mes")

    query = aplicar_filtro_cliente(Manutencao.query)

    inicio_mes_filtro = None

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

        except Exception:
            pass

    elif data_inicio and data_fim:
        try:
            inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
            fim = datetime.strptime(data_fim, "%Y-%m-%d")

            query = query.filter(
                Manutencao.data.between(inicio, fim)
            )

        except Exception:
            pass

    registros = query.all()

    por_mes = defaultdict(int)
    por_mes_corretiva = defaultdict(int)
    por_mes_preventiva = defaultdict(int)

    atendimento_counter = Counter()
    servicos_counter = Counter()
    causas_counter = Counter()

    for r in registros:

        if r.data:
            mes = r.data.strftime("%m-%Y")
            por_mes[mes] += 1
        else:
            continue

        atendimento = r.tipo_atendimento or "SEM INFO"
        atendimento_counter[atendimento] += 1

        tipo_servico = (r.tipo_servico or "").upper().strip()

        if tipo_servico == "CORRETIVA":
            por_mes_corretiva[mes] += 1
            servicos_counter["CORRETIVA"] += 1

        elif tipo_servico == "PREVENTIVA":
            por_mes_preventiva[mes] += 1
            servicos_counter["PREVENTIVA"] += 1

        causa = (r.causa or "").strip().upper()

        if causa in ["", "-", "NONE"]:
            causa = "SEM CAUSA"

        causas_counter[causa] += 1

    total = len(registros)
    corretivas = servicos_counter.get("CORRETIVA", 0)
    preventivas = servicos_counter.get("PREVENTIVA", 0)

    andamento = sum(
        1 for r in registros
        if "ANDAMENTO" in (r.status or "").upper()
    )

    ultimas_finalizacoes = [
        r for r in registros
        if "FINALIZADO" in (r.status or "").upper()
        and r.data_saida
    ]

    ultimas_finalizacoes = sorted(
        ultimas_finalizacoes,
        key=lambda r: (r.data_saida, r.id),
        reverse=True
    )[:5]

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

    causas = sorted(
        causas_counter.items(),
        key=lambda x: x[1],
        reverse=True
    )[:10]

    labels_frota = [c[0] for c in causas]
    valores_frota = [c[1] for c in causas]

    labels_atendimento = list(atendimento_counter.keys())
    valores_atendimento = list(atendimento_counter.values())

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