from flask import Blueprint, render_template, request, redirect
from models.manutencao import Manutencao
from database import db
from datetime import datetime

manutencao_bp = Blueprint("manutencao", __name__, url_prefix="/manutencoes")


# 📋 LISTAR (COM BUSCA INTELIGENTE)
@manutencao_bp.route("/")
def lista():

    busca = request.args.get("busca")

    query = Manutencao.query

    if busca:
        query = query.filter(
            db.or_(
                Manutencao.numero_frota.ilike(f"%{busca}%"),
                Manutencao.os.ilike(f"%{busca}%"),
                Manutencao.cliente.ilike(f"%{busca}%")
            )
        )

    registros = query.order_by(Manutencao.id.desc()).all()

    return render_template(
        "manutencoes/lista.html",
        registros=registros
    )


# ➕ NOVO
@manutencao_bp.route("/nova", methods=["GET", "POST"])
def nova():

    if request.method == "POST":

        data = request.form.get("data")

        try:
            data_convertida = datetime.strptime(data, "%Y-%m-%d") if data else None
        except:
            data_convertida = None

        m = Manutencao(
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

        db.session.add(m)
        db.session.commit()

        return redirect("/manutencoes/")

    return render_template("manutencoes/form.html", m=None)


# ✏️ EDITAR
@manutencao_bp.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):

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

        return redirect("/manutencoes/")

    return render_template("manutencoes/form.html", m=m)


# 🗑️ EXCLUIR
@manutencao_bp.route("/excluir/<int:id>")
def excluir(id):

    m = Manutencao.query.get_or_404(id)

    db.session.delete(m)
    db.session.commit()

    return redirect("/manutencoes/")