from flask import Blueprint, render_template, request, redirect, session
from models.usuario import Usuario
from database import db

auth_bp = Blueprint("auth", __name__)




# 🔐 LOGIN
@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")

        user = Usuario.query.filter_by(email=email).first()

        if user and user.check_senha(senha):
            session["user_id"] = user.id
            return redirect("/")

        return "Login inválido"

    return render_template("auth/login.html")




# 👤 CADASTRO
@auth_bp.route("/cadastro", methods=["GET", "POST"])
def cadastro():

    if request.method == "POST":
        nome = request.form.get("nome")
        email = request.form.get("email")
        senha = request.form.get("senha")

        user = Usuario(nome=nome, email=email)
        user.set_senha(senha)

        db.session.add(user)
        db.session.commit()  # 🔥 ESSENCIAL

        return redirect("/login")

    return render_template("auth/cadastro.html")

    if Usuario.query.filter_by(email=email).first():
        return "Email já cadastrado"





# 🔓 LOGOUT
@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

