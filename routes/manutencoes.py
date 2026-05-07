from flask import Blueprint, render_template, request, redirect, session, flash, jsonify
from models.manutencao import Manutencao
from models.cliente import Cliente
from models.afericao_termometro import AfericaoTermometro
from database import db
from datetime import datetime
import json
import os
import cloudinary
import cloudinary.uploader
from urllib.parse import urlparse

manutencao_bp = Blueprint("manutencao", __name__, url_prefix="/manutencoes")


# ==========================================
# 🔥 HELPERS CLOUDINARY
# ==========================================
def cloudinary_esta_configurado():
    return all([
        os.getenv("CLOUD_NAME"),
        os.getenv("API_KEY"),
        os.getenv("API_SECRET"),
    ])


# ==========================================
# 🔥 HELPERS IMAGENS
# ==========================================
def salvar_imagens():
    arquivos = request.files.getlist("imagens")
    return salvar_imagens_arquivos(arquivos)


def salvar_imagens_arquivos(arquivos):
    caminhos = []

    if not cloudinary_esta_configurado():
        print("⚠️ Cloudinary não configurado. Upload ignorado no ambiente atual.")
        return caminhos

    for arquivo in arquivos:
        if arquivo and arquivo.filename:
            try:
                upload = cloudinary.uploader.upload(arquivo)
                caminhos.append(upload["secure_url"])
            except Exception as e:
                print("❌ Erro ao enviar imagem para o Cloudinary:", e)

    return caminhos


def carregar_lista_imagens(valor):
    try:
        lista = json.loads(valor) if valor else []
        return lista if isinstance(lista, list) else []
    except:
        return []


def extrair_public_id_cloudinary(url):
    try:
        path = urlparse(url).path
        partes = path.split("/upload/")
        if len(partes) < 2:
            return None

        resto = partes[1]

        if resto.startswith("v") and "/" in resto:
            primeira, restante = resto.split("/", 1)
            if primeira[1:].isdigit():
                resto = restante

        if "." in resto:
            resto = resto.rsplit(".", 1)[0]

        return resto
    except:
        return None


# ==========================================
# 🔥 HELPERS AFERIÇÃO TERMÔMETRO
# ==========================================
def parse_data(valor):
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date() if valor else None
    except:
        return None


def calcular_dtm(data_entrada, data_saida):
    if not data_entrada or not data_saida:
        return None

    if data_saida < data_entrada:
        raise ValueError("A data de saída não pode ser menor que a data de entrada.")

    return (data_saida - data_entrada).days


def carregar_afericao(numero_frota, os, tipo_termometro):
    if not numero_frota or not os:
        return {
            "id": None,
            "afericao": "",
            "data_afericao": "",
            "status": "",
            "imagens": []
        }

    reg = AfericaoTermometro.query.filter_by(
        numero_frota=str(numero_frota).strip(),
        os=str(os).strip(),
        tipo_termometro=tipo_termometro
    ).first()

    if not reg:
        return {
            "id": None,
            "afericao": "",
            "data_afericao": "",
            "status": "",
            "imagens": []
        }

    return {
        "id": reg.id,
        "afericao": reg.afericao or "",
        "data_afericao": reg.data_afericao.strftime("%Y-%m-%d") if reg.data_afericao else "",
        "status": reg.status or "",
        "imagens": carregar_lista_imagens(reg.imagens)
    }


def salvar_ou_atualizar_afericao(
    numero_frota,
    os,
    tipo_termometro,
    afericao,
    data_afericao,
    status,
    novas_imagens=None
):
    if not numero_frota or not os:
        return

    numero_frota = str(numero_frota).strip()
    os = str(os).strip()
    novas_imagens = novas_imagens or []

    reg = AfericaoTermometro.query.filter_by(
        numero_frota=numero_frota,
        os=os,
        tipo_termometro=tipo_termometro
    ).first()

    imagens_atuais = carregar_lista_imagens(reg.imagens) if reg else []

    if not (
        str(afericao or "").strip()
        or data_afericao
        or str(status or "").strip()
        or imagens_atuais
        or novas_imagens
    ):
        if reg:
            db.session.delete(reg)
        return

    total_imagens = len(imagens_atuais) + len(novas_imagens)
    if total_imagens > 4:
        raise ValueError(
            f"O termômetro de {tipo_termometro.lower()} permite no máximo 4 imagens."
        )

    if not reg:
        reg = AfericaoTermometro(
            numero_frota=numero_frota,
            os=os,
            tipo_termometro=tipo_termometro
        )
        db.session.add(reg)

    reg.numero_frota = numero_frota
    reg.os = os
    reg.tipo_termometro = tipo_termometro
    reg.afericao = str(afericao).strip() if afericao else None
    reg.data_afericao = data_afericao
    reg.status = str(status).strip() if status else None
    reg.imagens = json.dumps(imagens_atuais + novas_imagens)


def mover_afericoes_se_trocar_frota_ou_os(numero_frota_antiga, os_antiga, numero_frota_nova, os_nova):
    if not numero_frota_antiga or not os_antiga:
        return

    regs = AfericaoTermometro.query.filter_by(
        numero_frota=str(numero_frota_antiga).strip(),
        os=str(os_antiga).strip()
    ).all()

    for reg in regs:
        reg.numero_frota = str(numero_frota_nova).strip() if numero_frota_nova else reg.numero_frota
        reg.os = str(os_nova).strip() if os_nova else reg.os


# ==========================================
# 🖼️ EXCLUIR IMAGEM MANUTENÇÃO (🔒 ADMIN) - AJAX
# ==========================================
@manutencao_bp.route("/<int:id>/excluir-imagem", methods=["POST"])
def excluir_imagem(id):

    if not session.get("user_id"):
        return jsonify({"ok": False, "message": "Sessão expirada."}), 401

    if session.get("user_role") != "admin":
        return jsonify({"ok": False, "message": "Sem permissão."}), 403

    m = Manutencao.query.get_or_404(id)

    imagem_url = request.form.get("imagem_url")
    if not imagem_url:
        return jsonify({"ok": False, "message": "Imagem não informada."}), 400

    imagens_atuais = carregar_lista_imagens(m.imagens)

    if imagem_url not in imagens_atuais:
        return jsonify({"ok": False, "message": "Imagem não encontrada nesse registro."}), 404

    imagens_atuais.remove(imagem_url)
    m.imagens = json.dumps(imagens_atuais)

    public_id = extrair_public_id_cloudinary(imagem_url)
    if public_id and cloudinary_esta_configurado():
        try:
            cloudinary.uploader.destroy(public_id)
        except Exception as e:
            print("Erro ao apagar imagem no Cloudinary:", e)

    db.session.commit()

    return jsonify({
        "ok": True,
        "message": "Imagem excluída com sucesso!",
        "restantes": len(imagens_atuais)
    })


# ==========================================
# 🖼️ EXCLUIR IMAGEM AFERIÇÃO (🔒 ADMIN) - AJAX
# ==========================================
@manutencao_bp.route("/afericao/<int:afericao_id>/excluir-imagem", methods=["POST"])
def excluir_imagem_afericao(afericao_id):

    if not session.get("user_id"):
        return jsonify({"ok": False, "message": "Sessão expirada."}), 401

    if session.get("user_role") != "admin":
        return jsonify({"ok": False, "message": "Sem permissão."}), 403

    afericao = AfericaoTermometro.query.get_or_404(afericao_id)

    imagem_url = request.form.get("imagem_url")
    if not imagem_url:
        return jsonify({"ok": False, "message": "Imagem não informada."}), 400

    imagens_atuais = carregar_lista_imagens(afericao.imagens)

    if imagem_url not in imagens_atuais:
        return jsonify({"ok": False, "message": "Imagem não encontrada nessa aferição."}), 404

    imagens_atuais.remove(imagem_url)
    afericao.imagens = json.dumps(imagens_atuais)

    public_id = extrair_public_id_cloudinary(imagem_url)
    if public_id and cloudinary_esta_configurado():
        try:
            cloudinary.uploader.destroy(public_id)
        except Exception as e:
            print("Erro ao apagar imagem da aferição no Cloudinary:", e)

    db.session.commit()

    return jsonify({
        "ok": True,
        "message": "Imagem da aferição excluída com sucesso!",
        "restantes": len(imagens_atuais)
    })


# ==========================================
# ➕ NOVA MANUTENÇÃO (🔒 ADMIN)
# ==========================================
@manutencao_bp.route("/", methods=["GET", "POST"])
def nova():

    if not session.get("user_id"):
        return redirect("/login")

    if session.get("user_role") != "admin":
        return redirect("/")

    if request.method == "POST":

        data_convertida = parse_data(request.form.get("data"))
        data_saida_convertida = parse_data(request.form.get("data_saida"))
        dtm_calculado = calcular_dtm(data_convertida, data_saida_convertida)
        caminhos_imagens = salvar_imagens()

        numero_frota = request.form.get("numero_frota")
        os_numero = request.form.get("os")

        placa_novas_imagens = salvar_imagens_arquivos(request.files.getlist("placa_imagens"))
        ambiente_novas_imagens = salvar_imagens_arquivos(request.files.getlist("ambiente_imagens"))

        nova_manutencao = Manutencao(
            data=data_convertida,
            data_saida=data_saida_convertida,
            dtm=dtm_calculado,
            numero_frota=numero_frota,
            bau=request.form.get("bau"),
            tipo_veiculo=request.form.get("tipo_veiculo"),
            tipo_servico=request.form.get("tipo_servico"),
            tipo_atendimento=request.form.get("tipo_atendimento"),
            tipo_manutencao=request.form.get("tipo_manutencao"),
            status=request.form.get("status"),
            observacao=request.form.get("observacao"),
            cliente=request.form.get("cliente"),
            os=os_numero,
            causa=request.form.get("causa"),
            imagens=json.dumps(caminhos_imagens)
        )

        try:
            db.session.add(nova_manutencao)

            salvar_ou_atualizar_afericao(
                numero_frota=numero_frota,
                os=os_numero,
                tipo_termometro="PLACA",
                afericao=request.form.get("placa_afericao"),
                data_afericao=parse_data(request.form.get("placa_data_afericao")),
                status=request.form.get("placa_status"),
                novas_imagens=placa_novas_imagens
            )

            salvar_ou_atualizar_afericao(
                numero_frota=numero_frota,
                os=os_numero,
                tipo_termometro="AMBIENTE",
                afericao=request.form.get("ambiente_afericao"),
                data_afericao=parse_data(request.form.get("ambiente_data_afericao")),
                status=request.form.get("ambiente_status"),
                novas_imagens=ambiente_novas_imagens
            )

            db.session.commit()

            flash("Manutenção salva com sucesso!", "success")
            return redirect("/manutencoes/lista")

        except ValueError as e:
            db.session.rollback()
            flash(str(e), "danger")
            return redirect(request.url)

    clientes = Cliente.query.order_by(Cliente.nome).all()

    return render_template(
        "manutencoes/form.html",
        clientes=clientes,
        m=None,
        imagens_lista=[],
        afericao_placa={"id": None, "afericao": "", "data_afericao": "", "status": "", "imagens": []},
        afericao_ambiente={"id": None, "afericao": "", "data_afericao": "", "status": "", "imagens": []}
    )


# ==========================================
# 📋 LISTA
# ==========================================
@manutencao_bp.route("/lista")
def lista():

    if not session.get("user_id"):
        return redirect("/login")

    filtro = request.args.get("filtro")
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")

    query = Manutencao.query

    if filtro == "andamento":
        query = query.filter(Manutencao.status.ilike("%ANDAMENTO%"))
    elif filtro == "corretiva":
        query = query.filter(Manutencao.tipo_servico.ilike("%CORRETIVA%"))
    elif filtro == "preventiva":
        query = query.filter(Manutencao.tipo_servico.ilike("%PREVENTIVA%"))

    if data_inicio and data_fim:
        try:
            inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
            fim = datetime.strptime(data_fim, "%Y-%m-%d")
            query = query.filter(Manutencao.data.between(inicio, fim))
        except:
            pass

    registros = query.order_by(
        Manutencao.data.desc().nullslast()
    ).all()

    for r in registros:
        afericao_placa = AfericaoTermometro.query.filter_by(
            numero_frota=str(r.numero_frota).strip() if r.numero_frota else "",
            os=str(r.os).strip() if r.os else "",
            tipo_termometro="PLACA"
        ).first()

        afericao_ambiente = AfericaoTermometro.query.filter_by(
            numero_frota=str(r.numero_frota).strip() if r.numero_frota else "",
            os=str(r.os).strip() if r.os else "",
            tipo_termometro="AMBIENTE"
        ).first()

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
        "manutencoes/lista.html",
        registros=registros
    )


# ==========================================
# ✏️ EDITAR (🔒 ADMIN)
# ==========================================
@manutencao_bp.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):

    if not session.get("user_id"):
        return redirect("/login")

    if session.get("user_role") != "admin":
        return redirect("/")

    m = Manutencao.query.get_or_404(id)

    if request.method == "POST":
        numero_frota_antiga = m.numero_frota
        os_antiga = m.os

        m.data = parse_data(request.form.get("data"))
        m.data_saida = parse_data(request.form.get("data_saida"))
        m.dtm = calcular_dtm(m.data, m.data_saida)

        novas_imagens = salvar_imagens()

        if novas_imagens:
            imagens_atuais = carregar_lista_imagens(m.imagens)
            m.imagens = json.dumps(imagens_atuais + novas_imagens)

        m.numero_frota = request.form.get("numero_frota")
        m.bau = request.form.get("bau")
        m.tipo_veiculo = request.form.get("tipo_veiculo")
        m.tipo_servico = request.form.get("tipo_servico")
        m.tipo_atendimento = request.form.get("tipo_atendimento")
        m.tipo_manutencao = request.form.get("tipo_manutencao")
        m.status = request.form.get("status")
        m.observacao = request.form.get("observacao")
        m.cliente = request.form.get("cliente")
        m.os = request.form.get("os")
        m.causa = request.form.get("causa")

        placa_novas_imagens = salvar_imagens_arquivos(request.files.getlist("placa_imagens"))
        ambiente_novas_imagens = salvar_imagens_arquivos(request.files.getlist("ambiente_imagens"))

        try:
            mover_afericoes_se_trocar_frota_ou_os(
                numero_frota_antiga=numero_frota_antiga,
                os_antiga=os_antiga,
                numero_frota_nova=m.numero_frota,
                os_nova=m.os
            )

            salvar_ou_atualizar_afericao(
                numero_frota=m.numero_frota,
                os=m.os,
                tipo_termometro="PLACA",
                afericao=request.form.get("placa_afericao"),
                data_afericao=parse_data(request.form.get("placa_data_afericao")),
                status=request.form.get("placa_status"),
                novas_imagens=placa_novas_imagens
            )

            salvar_ou_atualizar_afericao(
                numero_frota=m.numero_frota,
                os=m.os,
                tipo_termometro="AMBIENTE",
                afericao=request.form.get("ambiente_afericao"),
                data_afericao=parse_data(request.form.get("ambiente_data_afericao")),
                status=request.form.get("ambiente_status"),
                novas_imagens=ambiente_novas_imagens
            )

            db.session.commit()

            flash("Manutenção atualizada com sucesso!", "success")
            return redirect("/frotas/" + str(m.numero_frota))

        except ValueError as e:
            db.session.rollback()
            flash(str(e), "danger")
            return redirect(request.url)

    clientes = Cliente.query.order_by(Cliente.nome).all()
    imagens_lista = carregar_lista_imagens(m.imagens)

    afericao_placa = carregar_afericao(m.numero_frota, m.os, "PLACA")
    afericao_ambiente = carregar_afericao(m.numero_frota, m.os, "AMBIENTE")

    return render_template(
        "manutencoes/form.html",
        m=m,
        clientes=clientes,
        imagens_lista=imagens_lista,
        afericao_placa=afericao_placa,
        afericao_ambiente=afericao_ambiente
    )


# ==========================================
# 🗑️ EXCLUIR (🔒 ADMIN)
# ==========================================
@manutencao_bp.route("/excluir/<int:id>")
def excluir(id):

    if not session.get("user_id"):
        return redirect("/login")

    if session.get("user_role") != "admin":
        return redirect("/")

    m = Manutencao.query.get_or_404(id)

    if m.numero_frota and m.os:
        AfericaoTermometro.query.filter_by(
            numero_frota=str(m.numero_frota).strip(),
            os=str(m.os).strip()
        ).delete()

    db.session.delete(m)
    db.session.commit()

    flash("Manutenção excluída com sucesso!", "success")
    return redirect("/manutencoes/lista")