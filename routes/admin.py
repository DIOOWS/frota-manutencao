from flask import Blueprint, render_template, request, redirect, session
from models.usuario import Usuario
from models.cliente import Cliente
from database import db
from utils.auth import admin_required
import os
import cloudinary.uploader

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def cloudinary_configurado():
    return all([
        os.getenv("CLOUD_NAME"),
        os.getenv("API_KEY"),
        os.getenv("API_SECRET"),
    ])


# 👑 DASHBOARD
@admin_bp.route("/")
@admin_required
def dashboard_admin():
    return render_template("admin/dashboard.html")


# =========================================================
# 👥 USUÁRIOS
# =========================================================

@admin_bp.route("/usuarios")
@admin_required
def listar_usuarios():
    usuarios = Usuario.query.order_by(Usuario.id.desc()).all()
    return render_template("admin/usuarios.html", usuarios=usuarios)


@admin_bp.route("/usuarios/novo", methods=["GET", "POST"])
@admin_required
def novo_usuario():

    clientes = Cliente.query.order_by(Cliente.nome).all()

    if request.method == "POST":
        nome = request.form.get("nome")
        email = request.form.get("email")
        senha = request.form.get("senha")
        role = request.form.get("role")
        cliente_id = request.form.get("cliente_id")

        if not nome:
            return render_template(
                "admin/usuario_form.html",
                user=None,
                clientes=clientes,
                erro="Informe o nome do usuário."
            )

        if not senha:
            return render_template(
                "admin/usuario_form.html",
                user=None,
                clientes=clientes,
                erro="Informe a senha."
            )

        if role not in ["admin", "gestao", "gestor"] and not cliente_id:
            return render_template(
                "admin/usuario_form.html",
                user=None,
                clientes=clientes,
                erro="Selecione o cliente vinculado para este usuário."
            )

        if Usuario.query.filter_by(nome=nome).first():
            return render_template(
                "admin/usuario_form.html",
                user=None,
                clientes=clientes,
                erro="Usuário já existe."
            )

        user = Usuario(
            nome=nome,
            email=email,
            role=role,
            cliente_id=int(cliente_id) if cliente_id else None
        )

        user.set_senha(senha)

        foto = request.files.get("foto")
        if foto and foto.filename:
            if cloudinary_configurado():
                resultado = cloudinary.uploader.upload(foto)
                user.foto = resultado["secure_url"]
            else:
                print("Cloudinary não configurado. Foto ignorada no ambiente local.")

        db.session.add(user)
        db.session.commit()

        return redirect("/admin/usuarios")

    return render_template(
        "admin/usuario_form.html",
        user=None,
        clientes=clientes
    )


@admin_bp.route("/usuarios/editar/<int:id>", methods=["GET", "POST"])
@admin_required
def editar_usuario(id):

    user = Usuario.query.get_or_404(id)
    clientes = Cliente.query.order_by(Cliente.nome).all()

    if request.method == "POST":
        nome = request.form.get("nome")
        email = request.form.get("email")
        role = request.form.get("role")
        cliente_id = request.form.get("cliente_id")

        if not nome:
            return render_template(
                "admin/usuario_form.html",
                user=user,
                clientes=clientes,
                erro="Informe o nome do usuário."
            )

        if role not in ["admin", "gestao", "gestor"] and not cliente_id:
            return render_template(
                "admin/usuario_form.html",
                user=user,
                clientes=clientes,
                erro="Selecione o cliente vinculado para este usuário."
            )

        usuario_existente = Usuario.query.filter(
            Usuario.nome == nome,
            Usuario.id != user.id
        ).first()

        if usuario_existente:
            return render_template(
                "admin/usuario_form.html",
                user=user,
                clientes=clientes,
                erro="Já existe outro usuário com esse nome."
            )

        user.nome = nome
        user.email = email
        user.role = role
        user.cliente_id = int(cliente_id) if cliente_id else None

        senha = request.form.get("senha")
        if senha:
            user.set_senha(senha)

        foto = request.files.get("foto")
        if foto and foto.filename:
            if cloudinary_configurado():
                resultado = cloudinary.uploader.upload(foto)
                user.foto = resultado["secure_url"]
            else:
                print("Cloudinary não configurado. Foto ignorada no ambiente local.")

        db.session.commit()

        if user.id == session.get("user_id"):
            session["user_nome"] = user.nome
            session["user_name"] = user.nome
            session["user_role"] = user.role
            session["user_foto"] = user.foto
            session["cliente_id"] = user.cliente_id
            session["cliente_nome"] = user.cliente.nome if user.cliente else None

        return redirect("/admin/usuarios")

    return render_template(
        "admin/usuario_form.html",
        user=user,
        clientes=clientes
    )


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

@admin_bp.route("/clientes")
@admin_required
def listar_clientes():
    clientes = Cliente.query.order_by(Cliente.id.desc()).all()
    return render_template("admin/clientes.html", clientes=clientes)


@admin_bp.route("/clientes/novo", methods=["GET", "POST"])
@admin_required
def novo_cliente():

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


@admin_bp.route("/clientes/editar/<int:id>", methods=["GET", "POST"])
@admin_required
def editar_cliente(id):

    cliente = Cliente.query.get_or_404(id)

    if request.method == "POST":
        cliente.nome = request.form.get("nome")
        cliente.email = request.form.get("email")
        cliente.telefone = request.form.get("telefone")

        db.session.commit()
        return redirect("/admin/clientes")

    return render_template("admin/cliente_form.html", cliente=cliente)


@admin_bp.route("/clientes/excluir/<int:id>")
@admin_required
def excluir_cliente(id):

    cliente = Cliente.query.get_or_404(id)

    db.session.delete(cliente)
    db.session.commit()

    return redirect("/admin/clientes")