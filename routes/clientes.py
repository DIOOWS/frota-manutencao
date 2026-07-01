from flask import Blueprint, render_template, request, redirect, session, abort, flash
from models.cliente import Cliente
from database import db
import os
import cloudinary
import cloudinary.uploader

cliente_bp = Blueprint("cliente", __name__, url_prefix="/clientes")


# 🔒 FUNÇÃO DE PROTEÇÃO
def admin_only():
    if not session.get("user_id"):
        return redirect("/login")

    # 🔥 ADMIN E GESTÃO TÊM ACESSO
    if session.get("user_role") not in ["admin", "gestao", "gestor"]:
        abort(403)


def cloudinary_esta_configurado():
    return all([
        os.getenv("CLOUD_NAME"),
        os.getenv("API_KEY"),
        os.getenv("API_SECRET"),
    ])


def salvar_logo_cliente(arquivo):
    if not arquivo or not arquivo.filename:
        return None

    if not cloudinary_esta_configurado():
        raise RuntimeError(
            "Cloudinary não configurado. Configure CLOUD_NAME, API_KEY e API_SECRET para salvar a logo do cliente."
        )

    upload = cloudinary.uploader.upload(
        arquivo,
        folder="easy_control/clientes",
        resource_type="image"
    )

    return upload.get("secure_url")


# ==========================================
# 📋 LISTA
# ==========================================
@cliente_bp.route("/")
def lista():
    resp = admin_only()
    if resp:
        return resp

    clientes = Cliente.query.order_by(Cliente.nome.asc()).all()
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
        try:
            logo_url = salvar_logo_cliente(request.files.get("logo"))

            c = Cliente(
                nome=(request.form.get("nome") or "").strip(),
                telefone=(request.form.get("telefone") or "").strip(),
                email=(request.form.get("email") or "").strip(),
                logo=logo_url
            )

            db.session.add(c)
            db.session.commit()

            flash("Cliente salvo com sucesso!", "success")
            return redirect("/clientes/")

        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar cliente: {str(e)}", "danger")
            return redirect(request.url)

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
        try:
            cliente.nome = (request.form.get("nome") or "").strip()
            cliente.telefone = (request.form.get("telefone") or "").strip()
            cliente.email = (request.form.get("email") or "").strip()

            nova_logo = salvar_logo_cliente(request.files.get("logo"))
            if nova_logo:
                cliente.logo = nova_logo

            if request.form.get("remover_logo") == "1":
                cliente.logo = None

            db.session.commit()

            flash("Cliente atualizado com sucesso!", "success")
            return redirect("/clientes/")

        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao atualizar cliente: {str(e)}", "danger")
            return redirect(request.url)

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

    flash("Cliente excluído com sucesso!", "success")
    return redirect("/clientes/")
