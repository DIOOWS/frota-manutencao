from flask import Blueprint, render_template, request, redirect, session
from models.usuario import Usuario
from database import db
from utils.auth import admin_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# 👑 DASHBOARD
@admin_bp.route("/")
@admin_required
def dashboard_admin():
    return render_template("admin/dashboard.html")


# 👥 LISTAR USUÁRIOS
@admin_bp.route("/usuarios")
@admin_required
def listar_usuarios():
    usuarios = Usuario.query.order_by(Usuario.id.desc()).all()
    return render_template("admin/usuarios.html", usuarios=usuarios)


# ➕ NOVO USUÁRIO
@admin_bp.route("/usuarios/novo", methods=["GET", "POST"])
@admin_required
def novo_usuario():

    if request.method == "POST":
        nome = request.form.get("nome")
        email = request.form.get("email")
        senha = request.form.get("senha")
        role = request.form.get("role")

        # 🔒 valida duplicado
        if Usuario.query.filter_by(nome=nome).first():
            return render_template(
                "admin/usuario_form.html",
                user=None,
                erro="Usuário já existe"
            )

        user = Usuario(
            nome=nome,
            email=email,
            role=role
        )

        user.set_senha(senha)

        db.session.add(user)
        db.session.commit()

        return redirect("/admin/usuarios")

    # 🔥 FALTAVA ISSO
    return render_template("admin/usuario_form.html", user=None)


# ✏️ EDITAR
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

        db.session.commit()
        return redirect("/admin/usuarios")

    return render_template("admin/usuario_form.html", user=user)


# 🗑️ EXCLUIR
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