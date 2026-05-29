from flask import Blueprint, render_template, session, redirect
from models.manutencao import Manutencao
from models.afericao_termometro import AfericaoTermometro
from models.usuario import Usuario
from database import db
from collections import defaultdict
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
    Cliente comum visualiza somente frotas/placas ligadas ao cliente vinculado.
    """

    if usuario_eh_admin_ou_gestao():
        return query

    cliente_nome = nome_cliente_usuario_logado()

    if not cliente_nome:
        return query.filter(Manutencao.id == 0)

    return query.filter(
        db.func.upper(Manutencao.cliente) == cliente_nome.upper()
    )


# 🔧 PADRONIZA FROTA / PLACA
def formatar_frota(valor):
    try:
        return str(int(float(valor)))
    except Exception:
        return None


def formatar_placa(valor):
    valor = normalizar_texto(valor)
    if not valor:
        return None
    return valor.replace("-", "").replace(" ", "")


def identificador_veiculo(registro):
    """
    Prioridade: número da frota.
    Se não houver frota, usa a placa do veículo.
    """
    frota = formatar_frota(getattr(registro, "numero_frota", None))

    if frota:
        return {
            "codigo": frota,
            "tipo": "FROTA",
            "label": f"Frota {frota}",
            "classe": "frota-normal",
        }

    placa = formatar_placa(getattr(registro, "placa", None))

    if placa:
        return {
            "codigo": placa,
            "tipo": "PLACA",
            "label": f"Placa {placa}",
            "classe": "frota-placa",
        }

    return None


def carregar_lista_imagens(valor):
    try:
        lista = json.loads(valor) if valor else []
        return lista if isinstance(lista, list) else []
    except Exception:
        return []


def buscar_afericao(identificador, os, tipo_termometro):
    if not identificador or not os:
        return None

    return AfericaoTermometro.query.filter_by(
        numero_frota=str(identificador).strip(),
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


# 🔥 LISTA DE FROTAS / PLACAS
@frotas_bp.route("/")
def lista_frotas():

    if not session.get("user_id"):
        return redirect("/login")

    registros = aplicar_filtro_cliente(Manutencao.query).all()

    veiculos_map = {}
    meses_counter = defaultdict(int)

    for r in registros:
        ident = identificador_veiculo(r)

        if ident:
            codigo = ident["codigo"]

            if codigo not in veiculos_map:
                veiculos_map[codigo] = {
                    "codigo": codigo,
                    "tipo": ident["tipo"],
                    "label": ident["label"],
                    "classe": ident["classe"],
                    "qtd": 0,
                }

            veiculos_map[codigo]["qtd"] += 1

        if r.data:
            try:
                mes = r.data.strftime("%m-%Y")
                meses_counter[mes] += 1
            except Exception:
                pass

    frotas_ordenadas = sorted(
        veiculos_map.values(),
        key=lambda item: (
            0 if item["tipo"] == "FROTA" else 1,
            int(item["codigo"]) if str(item["codigo"]).isdigit() else 999999,
            str(item["codigo"])
        )
    )

    total_frotas = len(frotas_ordenadas)
    total_manutencoes = sum(item["qtd"] for item in frotas_ordenadas)

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


# 🔥 DETALHE DA FROTA / PLACA
@frotas_bp.route("/<veiculo>")
def detalhe_frota(veiculo):

    if not session.get("user_id"):
        return redirect("/login")

    veiculo = formatar_placa(veiculo)
    registros = aplicar_filtro_cliente(Manutencao.query).all()

    registros_filtrados = []
    tipo_identificador = "FROTA"

    for r in registros:
        ident = identificador_veiculo(r)
        if not ident:
            continue

        if ident["codigo"] == veiculo:
            registros_filtrados.append(r)
            tipo_identificador = ident["tipo"]

    registros = sorted(
        registros_filtrados,
        key=lambda x: parse_data_segura(x.data),
        reverse=True
    )

    for r in registros:
        ident = identificador_veiculo(r)
        identificador_afericao = ident["codigo"] if ident else None

        afericao_placa = buscar_afericao(identificador_afericao, r.os, "PLACA")
        afericao_ambiente = buscar_afericao(identificador_afericao, r.os, "AMBIENTE")

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
        frota=veiculo,
        tipo_identificador=tipo_identificador,
        registros=registros
    )
