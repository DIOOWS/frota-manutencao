from flask import Blueprint, render_template, request, redirect
from models.manutencao import Manutencao
from database import db

manutencao_bp = Blueprint("manutencao", __name__, url_prefix="/manutencoes")


# 📋 LISTAR (COM FILTRO)
@manutencao_bp.route("/")
def lista():

    frota = request.args.get("frota")

    query = Manutencao.query

    if frota:
        query = query.filter(  # 🔥 CORREÇÃO AQUI
            Manutencao.numero_frota.ilike(f"%{frota}%")
        )

    registros = query.all()  # agora usa o filtro corretamente

    return render_template(
        "manutencoes/lista.html",
        registros=registros
    )

# ➕ NOVO
@manutencao_bp.route("/nova", methods=["GET", "POST"])
def nova():

    if request.method == "POST":

        m = Manutencao(
            data=request.form["data"],
            numero_frota=request.form["numero_frota"],
            bau=request.form["bau"],
            tipo_veiculo=request.form["tipo_veiculo"],
            tipo_servico=request.form["tipo_servico"],
            tipo_atendimento=request.form["tipo_atendimento"],
            tipo_manutencao=request.form["tipo_manutencao"],
            status=request.form["status"],
            observacao=request.form["observacao"],
            cliente=request.form["cliente"],
        )

        db.session.add(m)
        db.session.commit()

        return redirect("/manutencoes")

    return render_template("manutencoes/form.html", m=None)


# ✏️ EDITAR
@manutencao_bp.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):

    m = Manutencao.query.get_or_404(id)

    if request.method == "POST":

        m.data = request.form["data"]
        m.numero_frota = request.form["numero_frota"]
        m.bau = request.form["bau"]
        m.tipo_veiculo = request.form["tipo_veiculo"]
        m.tipo_servico = request.form["tipo_servico"]
        m.tipo_atendimento = request.form["tipo_atendimento"]
        m.tipo_manutencao = request.form["tipo_manutencao"]
        m.status = request.form["status"]
        m.observacao = request.form["observacao"]
        m.cliente = request.form["cliente"]

        db.session.commit()

        return redirect("/manutencoes")

    return render_template("manutencoes/form.html", m=m)


# 🗑️ EXCLUIR
@manutencao_bp.route("/excluir/<int:id>")
def excluir(id):

    m = Manutencao.query.get_or_404(id)

    db.session.delete(m)
    db.session.commit()

    return redirect("/manutencoes")