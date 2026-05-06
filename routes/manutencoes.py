from flask import Blueprint, render_template, request, redirect, session, flash, current_app
from models.manutencao import Manutencao
from models.cliente import Cliente
from database import db
from datetime import datetime
from werkzeug.utils import secure_filename
import os
import json

manutencao_bp = Blueprint("manutencao", __name__, url_prefix="/manutencoes")


# ==========================================
# 🔥 SALVAR IMAGENS
# ==========================================
def salvar_imagens():
    arquivos = request.files.getlist("imagens")
    caminhos = []

    pasta_upload = current_app.config.get("UPLOAD_FOLDER")

    if not pasta_upload:
        pasta_upload = os.path.join(current_app.root_path, "static", "uploads")

    os.makedirs(pasta_upload, exist_ok=True)

    for arquivo in arquivos:
        if arquivo and arquivo.filename:
            nome_arquivo = secure_filename(arquivo.filename)

            caminho_completo = os.path.join(pasta_upload, nome_arquivo)
            arquivo.save(caminho_completo)

            caminhos.append("/static/uploads/" + nome_arquivo)

    return caminhos


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

        print("FILES RECEBIDOS:", request.files)
        print("IMAGENS:", request.files.getlist("imagens"))

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
        m=None
    )


# ==========================================
# 📋 LISTA
# ==========================================
@manutencao_bp.route("/lista")
def lista():

    if not session.get("user_id"):
        return redirect("/login")

    filtro = request.args.get("filtro")

    query = Manutencao.query

    if filtro == "andamento":
        query = query.filter(Manutencao.status.ilike("%ANDAMENTO%"))

    elif filtro == "corretiva":
        query = query.filter(Manutencao.tipo_servico.ilike("%CORRETIVA%"))

    elif filtro == "preventiva":
        query = query.filter(Manutencao.tipo_servico.ilike("%PREVENTIVA%"))

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
            try:
                imagens_atuais = json.loads(m.imagens) if m.imagens else []
            except:
                imagens_atuais = []

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

    return render_template(
        "manutencoes/form.html",
        m=m,
        clientes=clientes
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