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

    return render_template("clientes/form.html")