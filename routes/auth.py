from flask import Blueprint, render_template, request, redirect, session
from models.usuario import Usuario
from database import db

auth_bp = Blueprint("auth", __name__)


# 🔐 LOGIN
@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if session.get("user_id"):
        return redirect("/")

    if request.method == "POST":
        nome = request.form.get("nome")
        senha = request.form.get("senha")

        user = Usuario.query.filter_by(nome=nome).first()

        if user and user.check_senha(senha):
            session["user_id"] = user.id
            session["user_nome"] = user.nome
            session["user_role"] = user.role  # 🔥 AQUI ESTÁ O SEGREDO
            session["user_foto"] = user.foto

            return redirect("/")

        return render_template(
            "auth/login.html",
            erro="Usuário ou senha inválidos"
        )

    return render_template("auth/login.html")


# 🔓 LOGOUT
@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect("/login")