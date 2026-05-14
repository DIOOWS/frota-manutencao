from flask import Blueprint, render_template, request, redirect, session, abort
from models.cliente import Cliente
from database import db

cliente_bp = Blueprint("cliente", __name__, url_prefix="/clientes")


# 🔒 FUNÇÃO DE PROTEÇÃO
def admin_only():
    if not session.get("user_id"):
        return redirect("/login")

    # 🔥 ADMIN E GESTÃO TÊM ACESSO
    if session.get("user_role") not in ["admin", "gestao"]:
        abort(403)


# ==========================================
# 📋 LISTA
# ==========================================
@cliente_bp.route("/")
def lista():
    resp = admin_only()
    if resp:
        return resp

    clientes = Cliente.query.all()
    return render_template("clientes/lista.html", clientes=clientes)


# ==========================================
# ➕ NOVO
# ==========================================
@cliente_bp.route("/novo", methods=["GET", "POST"])
def novo():
    resp = admin_only()
    if resp:
        return resp

    if request.method == "POST":
        c = Cliente(
            nome=request.form.get("nome"),
            telefone=request.form.get("telefone"),
            email=request.form.get("email")
        )

        db.session.add(c)
        db.session.commit()

        return redirect("/clientes/")

    return render_template("clientes/form.html", cliente=None)


# ==========================================
# ✏️ EDITAR
# ==========================================
@cliente_bp.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    resp = admin_only()
    if resp:
        return resp

    cliente = Cliente.query.get_or_404(id)

    if request.method == "POST":
        cliente.nome = request.form.get("nome")
        cliente.telefone = request.form.get("telefone")
        cliente.email = request.form.get("email")

        db.session.commit()

        return redirect("/clientes/")

    return render_template("clientes/form.html", cliente=cliente)


# ==========================================
# 🗑️ EXCLUIR
# ==========================================
@cliente_bp.route("/excluir/<int:id>")
def excluir(id):
    resp = admin_only()
    if resp:
        return resp

    cliente = Cliente.query.get_or_404(id)

    db.session.delete(cliente)
    db.session.commit()

    return redirect("/clientes/")