from flask import Blueprint, render_template, request, redirect, session
from models.usuario import Usuario
from database import db
from utils.auth import admin_required
from werkzeug.utils import secure_filename
import os
import cloudinary.uploader

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# 👑 DASHBOARD
@admin_bp.route("/")
@admin_required
def dashboard_admin():
    return render_template("admin/dashboard.html")


# =========================================================
# 👥 USUÁRIOS
# =========================================================

# LISTAR
@admin_bp.route("/usuarios")
@admin_required
def listar_usuarios():
    usuarios = Usuario.query.order_by(Usuario.id.desc()).all()
    return render_template("admin/usuarios.html", usuarios=usuarios)


# NOVO
@admin_bp.route("/usuarios/novo", methods=["GET", "POST"])
@admin_required
def novo_usuario():

    if request.method == "POST":
        nome = request.form.get("nome")
        email = request.form.get("email")
        senha = request.form.get("senha")
        role = request.form.get("role")

        if Usuario.query.filter_by(nome=nome).first():
            return render_template(
                "admin/usuario_form.html",
                user=None,
                erro="Usuário já existe"
            )

        user = Usuario(nome=nome, email=email, role=role)
        user.set_senha(senha)

        # FOTO
        foto = request.files.get("foto")
        if foto and foto.filename:
            resultado = cloudinary.uploader.upload(foto)
            user.foto = resultado["secure_url"]

        db.session.add(user)
        db.session.commit()

        return redirect("/admin/usuarios")

    return render_template("admin/usuario_form.html", user=None)


# EDITAR
@admin_bp.route("/usuarios/editar/<int:id>", methods=["GET", "POST"])
@admin_required
def editar_usuario(id):

    user = Usuario.query.get_or_404(id)

    if request.method == "POST":
        user.nome = request.form.get("nome")
        user.email = request.form.get("email")
        user.role = request.form.get("role")

        senha = request.form.get("senha")
        if senha:
            user.set_senha(senha)

        foto = request.files.get("foto")
        if foto and foto.filename:
            resultado = cloudinary.uploader.upload(foto)
            user.foto = resultado["secure_url"]

        db.session.commit()

        # 🔥 ATUALIZA FOTO NA SESSÃO
        if user.id == session.get("user_id"):
            session["user_foto"] = user.foto

        return redirect("/admin/usuarios")

    return render_template("admin/usuario_form.html", user=user)


# EXCLUIR
@admin_bp.route("/usuarios/excluir/<int:id>")
@admin_required
def excluir_usuario(id):
    user = Usuario.query.get_or_404(id)

    if user.id == session.get("user_id"):
        return "Você não pode excluir a si mesmo 🚫"

    if user.role == "admin":
        total_admins = Usuario.query.filter_by(role="admin").count()
        if total_admins <= 1:
            return "Não é possível excluir o último admin 🚫"

    db.session.delete(user)
    db.session.commit()

    return redirect("/admin/usuarios")


# =========================================================
# 🧾 CLIENTES
# =========================================================

# LISTAR
@admin_bp.route("/clientes")
@admin_required
def listar_clientes():
    from models.cliente import Cliente

    clientes = Cliente.query.order_by(Cliente.id.desc()).all()
    return render_template("admin/clientes.html", clientes=clientes)


# NOVO
@admin_bp.route("/clientes/novo", methods=["GET", "POST"])
@admin_required
def novo_cliente():
    from models.cliente import Cliente

    if request.method == "POST":
        nome = request.form.get("nome")
        email = request.form.get("email")
        telefone = request.form.get("telefone")

        cliente = Cliente(
            nome=nome,
            email=email,
            telefone=telefone
        )

        db.session.add(cliente)
        db.session.commit()

        return redirect("/admin/clientes")

    return render_template("admin/cliente_form.html", cliente=None)


# EDITAR
@admin_bp.route("/clientes/editar/<int:id>", methods=["GET", "POST"])
@admin_required
def editar_cliente(id):
    from models.cliente import Cliente

    cliente = Cliente.query.get_or_404(id)

    if request.method == "POST":
        cliente.nome = request.form.get("nome")
        cliente.email = request.form.get("email")
        cliente.telefone = request.form.get("telefone")

        db.session.commit()
        return redirect("/admin/clientes")

    return render_template("admin/cliente_form.html", cliente=cliente)


# EXCLUIR
@admin_bp.route("/clientes/excluir/<int:id>")
@admin_required
def excluir_cliente(id):
    from models.cliente import Cliente

    cliente = Cliente.query.get_or_404(id)

    db.session.delete(cliente)
    db.session.commit()

    return redirect("/admin/clientes")