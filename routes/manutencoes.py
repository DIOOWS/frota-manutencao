from flask import Blueprint, render_template, request, redirect, session, flash, jsonify
from models.manutencao import Manutencao
from models.cliente import Cliente
from database import db
from datetime import datetime
import json
import cloudinary
import cloudinary.uploader
from urllib.parse import urlparse

manutencao_bp = Blueprint("manutencao", __name__, url_prefix="/manutencoes")


# ==========================================
# 🔥 HELPERS IMAGENS
# ==========================================
def salvar_imagens():
    arquivos = request.files.getlist("imagens")
    caminhos = []

    for arquivo in arquivos:
        if arquivo and arquivo.filename:
            upload = cloudinary.uploader.upload(arquivo)
            caminhos.append(upload["secure_url"])

    return caminhos


def carregar_lista_imagens(valor):
    try:
        lista = json.loads(valor) if valor else []
        return lista if isinstance(lista, list) else []
    except:
        return []


def extrair_public_id_cloudinary(url):
    """
    Exemplo:
    https://res.cloudinary.com/.../image/upload/v123456/pasta/arquivo.jpg

    Retorna:
    pasta/arquivo
    """
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
# 🖼️ EXCLUIR IMAGEM (🔒 ADMIN) - AJAX
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
    if public_id:
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
# ➕ NOVA MANUTENÇÃO (🔒 ADMIN)
# ==========================================
@manutencao_bp.route("/", methods=["GET", "POST"])
def nova():

    if not session.get("user_id"):
        return redirect("/login")

    if session.get("user_role") != "admin":
        return redirect("/")

    if request.method == "POST":

        data = request.form.get("data")
        data_saida = request.form.get("data_saida")

        try:
            data_convertida = datetime.strptime(data, "%Y-%m-%d") if data else None
        except:
            data_convertida = None

        try:
            data_saida_convertida = datetime.strptime(data_saida, "%Y-%m-%d") if data_saida else None
        except:
            data_saida_convertida = None

        caminhos_imagens = salvar_imagens()

        nova_manutencao = Manutencao(
            data=data_convertida,
            data_saida=data_saida_convertida,
            numero_frota=request.form.get("numero_frota"),
            bau=request.form.get("bau"),
            tipo_veiculo=request.form.get("tipo_veiculo"),
            tipo_servico=request.form.get("tipo_servico"),
            tipo_atendimento=request.form.get("tipo_atendimento"),
            tipo_manutencao=request.form.get("tipo_manutencao"),
            status=request.form.get("status"),
            observacao=request.form.get("observacao"),
            cliente=request.form.get("cliente"),
            os=request.form.get("os"),
            causa=request.form.get("causa"),
            imagens=json.dumps(caminhos_imagens)
        )

        db.session.add(nova_manutencao)
        db.session.commit()

        flash("Manutenção salva com sucesso!", "success")
        return redirect("/manutencoes/lista")

    clientes = Cliente.query.order_by(Cliente.nome).all()

    return render_template(
        "manutencoes/form.html",
        clientes=clientes,
        m=None,
        imagens_lista=[]
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

        data = request.form.get("data")
        data_saida = request.form.get("data_saida")

        try:
            m.data = datetime.strptime(data, "%Y-%m-%d") if data else None
        except:
            m.data = None

        try:
            m.data_saida = datetime.strptime(data_saida, "%Y-%m-%d") if data_saida else None
        except:
            m.data_saida = None

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

        db.session.commit()

        flash("Manutenção atualizada com sucesso!", "success")
        return redirect("/frotas/" + str(m.numero_frota))

    clientes = Cliente.query.order_by(Cliente.nome).all()
    imagens_lista = carregar_lista_imagens(m.imagens)

    return render_template(
        "manutencoes/form.html",
        m=m,
        clientes=clientes,
        imagens_lista=imagens_lista
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

    db.session.delete(m)
    db.session.commit()

    flash("Manutenção excluída com sucesso!", "success")
    return redirect("/manutencoes/lista")