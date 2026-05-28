from flask import Blueprint, render_template, session, redirect
from models.manutencao import Manutencao
from models.afericao_termometro import AfericaoTermometro
from models.usuario import Usuario
from database import db
from collections import Counter, defaultdict
from datetime import datetime
import json

frotas_bp = Blueprint("frotas", __name__, url_prefix="/frotas")


# 🔐 HELPERS MULTI-CLIENTE
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
    """
    Admin/Gestão/Gestor visualizam tudo.
    Cliente comum visualiza somente frotas ligadas ao cliente vinculado.
    """

    if usuario_eh_admin_ou_gestao():
        return query

    cliente_nome = nome_cliente_usuario_logado()

    if not cliente_nome:
        return query.filter(Manutencao.id == 0)

    return query.filter(
        db.func.upper(Manutencao.cliente) == cliente_nome.upper()
    )


# 🔧 PADRONIZA FROTA
def formatar_frota(valor):
    try:
        return str(int(float(valor)))
    except Exception:
        return "Sem frota"


def carregar_lista_imagens(valor):
    try:
        lista = json.loads(valor) if valor else []
        return lista if isinstance(lista, list) else []
    except Exception:
        return []


def buscar_afericao(numero_frota, os, tipo_termometro):
    if not numero_frota or not os:
        return None

    return AfericaoTermometro.query.filter_by(
        numero_frota=str(numero_frota).strip(),
        os=str(os).strip(),
        tipo_termometro=tipo_termometro
    ).first()


def parse_data_segura(data):
    if not data:
        return datetime.min

    if isinstance(data, datetime):
        return data

    try:
        return datetime.strptime(str(data), "%Y-%m-%d")
    except Exception:
        return datetime.min


# 🔥 LISTA DE FROTAS
@frotas_bp.route("/")
def lista_frotas():

    if not session.get("user_id"):
        return redirect("/login")

    registros = aplicar_filtro_cliente(Manutencao.query).all()

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
            except Exception:
                pass

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

    registros = aplicar_filtro_cliente(Manutencao.query).all()

    registros = [
        r for r in registros
        if formatar_frota(r.numero_frota) == frota
    ]

    registros = sorted(
        registros,
        key=lambda x: parse_data_segura(x.data),
        reverse=True
    )

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