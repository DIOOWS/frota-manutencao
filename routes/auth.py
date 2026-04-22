from flask import Blueprint, render_template, request, redirect, session
from models.usuario import Usuario
from database import db

auth_bp = Blueprint("auth", __name__)


# 🔐 LOGIN
@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    # se já estiver logado → vai pro dashboard
    if session.get("user_id"):
        return redirect("/")

    if request.method == "POST":
        nome = request.form.get("nome")
        senha = request.form.get("senha")

        user = Usuario.query.filter_by(nome=nome).first()

        if user and user.check_senha(senha):
            session["user_id"] = user.id
            session["user_nome"] = user.nome  # 🔥 importante pra mostrar no sistema
            return redirect("/")

        return render_template(
            "auth/login.html",
            erro="Usuário ou senha inválidos"
        )

    return render_template("auth/login.html")


# 👤 CADASTRO (SÓ LOGADO)
@auth_bp.route("/cadastro", methods=["GET", "POST"])
def cadastro():

    # 🔐 só permite se estiver logado
    if not session.get("user_id"):
        return redirect("/login")

    if request.method == "POST":
        nome = request.form.get("nome")
        email = request.form.get("email")
        senha = request.form.get("senha")

        if not nome:
            return render_template(
                "auth/cadastro.html",
                erro="Nome é obrigatório"
            )

        if Usuario.query.filter_by(nome=nome).first():
            return render_template(
                "auth/cadastro.html",
                erro="Usuário já existe"
            )

        user = Usuario(
            nome=nome,
            email=email
        )

        user.set_senha(senha)

        db.session.add(user)
        db.session.commit()

        return render_template(
            "auth/cadastro.html",
            sucesso="Usuário cadastrado com sucesso!"
        )

    return render_template("auth/cadastro.html")


# 🔓 LOGOUT
@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect("/login")