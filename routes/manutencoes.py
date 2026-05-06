from flask import Blueprint, render_template, request, redirect, session, flash
from models.manutencao import Manutencao
from models.cliente import Cliente
from database import db
from datetime import datetime

manutencao_bp = Blueprint("manutencao", __name__, url_prefix="/manutencoes")


# ==========================================
# ➕ NOVA MANUTENÇÃO (🔒 ADMIN)
# ==========================================
@manutencao_bp.route("/", methods=["GET", "POST"])
def nova():

    if not session.get("user_id"):
        return redirect("/login")

    # 🔥 BLOQUEIO
    if session.get("user_role") != "admin":
        return redirect("/")

    if request.method == "POST":

        data = request.form.get("data")

        try:
            data_convertida = datetime.strptime(data, "%Y-%m-%d") if data else None
        except:
            data_convertida = None

        nova = Manutencao(
            data=data_convertida,
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
        )

        db.session.add(nova)
        db.session.commit()

        flash("Manutenção salva com sucesso!", "success")

        return redirect("/manutencoes/lista")

    clientes = Cliente.query.order_by(Cliente.nome).all()

    return render_template(
        "manutencoes/form.html",
        clientes=clientes
    )


# ==========================================
# 📋 LISTA (LIBERADO)
# ==========================================
@manutencao_bp.route("/lista")
def lista():

    if not session.get("user_id"):
        return redirect("/login")

    registros = Manutencao.query.order_by(
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

    # 🔥 BLOQUEIO
    if session.get("user_role") != "admin":
        return redirect("/")

    m = Manutencao.query.get_or_404(id)

    if request.method == "POST":

        data = request.form.get("data")

        try:
            m.data = datetime.strptime(data, "%Y-%m-%d") if data else None
        except:
            m.data = None

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

    # 🔥 BLOQUEIO
    if session.get("user_role") != "admin":
        return redirect("/")

    m = Manutencao.query.get_or_404(id)

    db.session.delete(m)
    db.session.commit()

    flash("Manutenção excluída com sucesso!", "success")

    return redirect("/manutencoes/lista")