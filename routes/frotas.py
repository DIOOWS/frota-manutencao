from flask import Blueprint, render_template, session, redirect
from models.manutencao import Manutencao
from collections import Counter
from datetime import datetime

frotas_bp = Blueprint("frotas", __name__, url_prefix="/frotas")


# 🔧 PADRONIZA FROTA
def formatar_frota(valor):
    try:
        return str(int(float(valor)))
    except:
        return "Sem frota"


# 🔥 LISTA DE FROTAS
@frotas_bp.route("/")
def lista_frotas():

    if not session.get("user_id"):
        return redirect("/login")

    registros = Manutencao.query.with_entities(Manutencao.numero_frota).all()

    frotas = Counter(
        formatar_frota(r.numero_frota) for r in registros
    )

    frotas_ordenadas = sorted(
        frotas.items(),
        key=lambda x: int(x[0]) if x[0].isdigit() else 0
    )

    return render_template(
        "frotas_lista.html",
        frotas=frotas_ordenadas
    )


# 🔥 DETALHE DA FROTA (CORRIGIDO)
@frotas_bp.route("/<frota>")
def detalhe_frota(frota):

    if not session.get("user_id"):
        return redirect("/login")

    # 🔥 pega tudo e filtra corretamente
    registros = [
        r for r in Manutencao.query.all()
        if formatar_frota(r.numero_frota) == frota
    ]

    # 🔥 função segura pra data
    def parse_data(data):
        if isinstance(data, datetime):
            return data
        try:
            return datetime.strptime(str(data), "%Y-%m-%d")
        except:
            return datetime.min

    # 🔥 ordena corretamente (mais novo → mais antigo)
    registros = sorted(
        registros,
        key=lambda x: parse_data(x.data),
        reverse=True
    )

    return render_template(
        "frotas_detalhe.html",
        frota=frota,
        registros=registros
    )