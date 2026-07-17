from datetime import datetime, timedelta

from flask import Blueprint, jsonify, redirect, render_template, request, session

from database import db
from models.usuario import Usuario


auth_bp = Blueprint("auth", __name__)

ROLES_QUE_VISUALIZAM_ONLINE = {"admin", "gestao", "gestor"}
TEMPO_ONLINE_SEGUNDOS = 90


def _agora_utc():
    """Retorna UTC sem timezone para funcionar igualmente em SQLite e PostgreSQL."""
    return datetime.utcnow()


def _usuario_logado():
    user_id = session.get("user_id")

    if not user_id:
        return None

    return db.session.get(Usuario, user_id)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if session.get("user_id"):
        return redirect("/")

    if request.method == "POST":
        nome = (request.form.get("nome") or "").strip()
        senha = request.form.get("senha") or ""

        user = Usuario.query.filter_by(nome=nome).first()

        if user and user.check_senha(senha):
            session["user_id"] = user.id
            session["user_nome"] = user.nome
            session["user_name"] = user.nome
            session["user_role"] = user.role
            session["user_foto"] = user.foto
            session["cliente_id"] = user.cliente_id
            session["cliente_nome"] = user.cliente.nome if user.cliente else None

            user.ultima_atividade = _agora_utc()
            db.session.commit()

            return redirect("/")

        return render_template(
            "auth/login.html",
            erro="Usuário ou senha inválidos"
        )

    return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    user = _usuario_logado()

    if user:
        user.ultima_atividade = None
        db.session.commit()

    session.clear()
    return redirect("/login")


@auth_bp.route("/api/presenca", methods=["POST"])
def registrar_presenca():
    """Heartbeat chamado pelo navegador a cada 30 segundos."""
    user = _usuario_logado()

    if not user:
        session.clear()
        return jsonify({"ok": False, "erro": "nao_autenticado"}), 401

    user.ultima_atividade = _agora_utc()
    db.session.commit()

    return jsonify({"ok": True})


@auth_bp.route("/api/usuarios-online", methods=["GET"])
def usuarios_online():
    """Retorna somente nomes e quantidade; acesso restrito à gestão."""
    if not session.get("user_id"):
        return jsonify({"ok": False, "erro": "nao_autenticado"}), 401

    if session.get("user_role") not in ROLES_QUE_VISUALIZAM_ONLINE:
        return jsonify({"ok": False, "erro": "acesso_negado"}), 403

    limite = _agora_utc() - timedelta(seconds=TEMPO_ONLINE_SEGUNDOS)

    usuarios = (
        Usuario.query
        .filter(
            Usuario.ultima_atividade.isnot(None),
            Usuario.ultima_atividade >= limite
        )
        .order_by(Usuario.nome.asc())
        .all()
    )

    return jsonify({
        "ok": True,
        "total": len(usuarios),
        "usuarios": [
            {
                "id": usuario.id,
                "nome": usuario.nome
            }
            for usuario in usuarios
        ]
    })
