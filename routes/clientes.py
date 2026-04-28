from flask import Blueprint, render_template, request, redirect
from models.cliente import Cliente
from database import db

cliente_bp = Blueprint("cliente", __name__, url_prefix="/clientes")


# 📋 LISTA
@cliente_bp.route("/")
def lista():
    clientes = Cliente.query.all()
    return render_template("clientes/lista.html", clientes=clientes)


# ➕ NOVO
@cliente_bp.route("/novo", methods=["GET", "POST"])
def novo():

    if request.method == "POST":
        c = Cliente(
            nome=request.form.get("nome"),
            telefone=request.form.get("telefone"),
            email=request.form.get("email")
        )

        db.session.add(c)
        db.session.commit()

        return redirect("/clientes/")

    return render_template(
        "clientes/form.html",
        cliente=None  # 🔥 CORRETO
    )


# ✏️ EDITAR
@cliente_bp.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):

    cliente = Cliente.query.get_or_404(id)

    if request.method == "POST":
        cliente.nome = request.form.get("nome")
        cliente.telefone = request.form.get("telefone")
        cliente.email = request.form.get("email")

        db.session.commit()

        return redirect("/clientes/")

    return render_template(
        "clientes/form.html",
        cliente=cliente  # 🔥 AQUI FUNCIONA
    )


# 🗑️ EXCLUIR
@cliente_bp.route("/excluir/<int:id>")
def excluir(id):

    cliente = Cliente.query.get_or_404(id)

    db.session.delete(cliente)
    db.session.commit()

    return redirect("/clientes/")