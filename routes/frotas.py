from flask import Blueprint, render_template, session, redirect
from models.manutencao import Manutencao
from collections import Counter
from sqlalchemy import cast, String
from datetime import datetime

frotas_bp = Blueprint("frotas", __name__, url_prefix="/frotas")


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

    return render_template("frotas_lista.html", frotas=frotas_ordenadas)


# 🔥 DETALHE DA FROTA
@frotas_bp.route("/<frota>")
def detalhe_frota(frota):

    if not session.get("user_id"):
        return redirect("/login")

    def parse_data(data):
        if isinstance(data, datetime):
            return data
        try:
            return datetime.strptime(str(data), "%Y-%m-%d")
        except:
            return datetime.min

    registros = sorted(
        Manutencao.query.filter(
            cast(Manutencao.numero_frota, String) == frota
        ).all(),
        key=lambda x: parse_data(x.data),
        reverse=True
    )

    return render_template(
        "frotas_detalhe.html",
        frota=frota,
        registros=registros
    )