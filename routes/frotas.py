from flask import Blueprint, render_template, session, redirect
from models.manutencao import Manutencao
from models.afericao_termometro import AfericaoTermometro
from collections import Counter, defaultdict
from datetime import datetime
import json

frotas_bp = Blueprint("frotas", __name__, url_prefix="/frotas")


# 🔧 PADRONIZA FROTA
def formatar_frota(valor):
    try:
        return str(int(float(valor)))
    except:
        return "Sem frota"


def carregar_lista_imagens(valor):
    try:
        lista = json.loads(valor) if valor else []
        return lista if isinstance(lista, list) else []
    except:
        return []


def buscar_afericao(numero_frota, os, tipo_termometro):
    if not numero_frota or not os:
        return None

    return AfericaoTermometro.query.filter_by(
        numero_frota=str(numero_frota).strip(),
        os=str(os).strip(),
        tipo_termometro=tipo_termometro
    ).first()


def montar_status_afericao(status):
    if not status:
        return "-"
    return status


def parse_data_segura(data):
    if not data:
        return None

    if isinstance(data, datetime):
        return data

    try:
        return datetime.strptime(str(data), "%Y-%m-%d")
    except:
        return None


# 🔥 LISTA DE FROTAS
@frotas_bp.route("/")
def lista_frotas():

    if not session.get("user_id"):
        return redirect("/login")

    registros = Manutencao.query.all()

    frotas_counter = Counter()
    meses_counter = defaultdict(int)

    for r in registros:

        frota_formatada = formatar_frota(r.numero_frota)

        if frota_formatada and frota_formatada != "Sem frota":
            frotas_counter[frota_formatada] += 1

        if r.data:
            try:
                mes = r.data.strftime("%m-%Y")
                meses_counter[mes] += 1
            except:
                pass

    # Ordena por número da frota
    frotas_ordenadas = sorted(
        frotas_counter.items(),
        key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0
    )

    total_frotas = len(frotas_ordenadas)
    total_manutencoes = sum(frotas_counter.values())

    media_por_frota = round(total_manutencoes / total_frotas, 1) if total_frotas else 0

    if meses_counter:
        mes_mais_manutencoes, qtd_mes_mais_manutencoes = max(
            meses_counter.items(),
            key=lambda x: x[1]
        )
    else:
        mes_mais_manutencoes = "-"
        qtd_mes_mais_manutencoes = 0

    return render_template(
        "frotas_lista.html",
        frotas=frotas_ordenadas,
        total_frotas=total_frotas,
        total_manutencoes=total_manutencoes,
        media_por_frota=media_por_frota,
        mes_mais_manutencoes=mes_mais_manutencoes,
        qtd_mes_mais_manutencoes=qtd_mes_mais_manutencoes
    )


# 🔥 DETALHE DA FROTA
@frotas_bp.route("/<frota>")
def detalhe_frota(frota):

    if not session.get("user_id"):
        return redirect("/login")

    registros = [
        r for r in Manutencao.query.all()
        if formatar_frota(r.numero_frota) == frota
    ]

    def parse_data(data):
        if isinstance(data, datetime):
            return data
        try:
            return datetime.strptime(str(data), "%Y-%m-%d")
        except:
            return datetime.min

    registros = sorted(
        registros,
        key=lambda x: parse_data(x.data),
        reverse=True
    )

    # Injeta aferições em cada manutenção
    for r in registros:
        afericao_placa = buscar_afericao(r.numero_frota, r.os, "PLACA")
        afericao_ambiente = buscar_afericao(r.numero_frota, r.os, "AMBIENTE")

        r.placa_afericao = afericao_placa.afericao if afericao_placa else None
        r.placa_data_afericao = (
            afericao_placa.data_afericao.strftime("%d/%m/%Y")
            if afericao_placa and afericao_placa.data_afericao else None
        )
        r.placa_status = afericao_placa.status if afericao_placa else None
        r.placa_imagens = carregar_lista_imagens(afericao_placa.imagens) if afericao_placa else []

        r.ambiente_afericao = afericao_ambiente.afericao if afericao_ambiente else None
        r.ambiente_data_afericao = (
            afericao_ambiente.data_afericao.strftime("%d/%m/%Y")
            if afericao_ambiente and afericao_ambiente.data_afericao else None
        )
        r.ambiente_status = afericao_ambiente.status if afericao_ambiente else None
        r.ambiente_imagens = carregar_lista_imagens(afericao_ambiente.imagens) if afericao_ambiente else []

        r.imagens_lista = carregar_lista_imagens(r.imagens)

    return render_template(
        "frotas_detalhe.html",
        frota=frota,
        registros=registros
    )