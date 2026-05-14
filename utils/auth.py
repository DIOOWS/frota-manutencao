from functools import wraps
from flask import session, redirect


ROLES_GESTAO = ["gestao", "gestor"]
ROLES_ADMINISTRATIVAS = ["admin", "gestao", "gestor"]


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        if not session.get("user_id"):
            return redirect("/login")

        return f(*args, **kwargs)

    return decorated_function


def is_gestao():
    return session.get("user_role") in ROLES_GESTAO


def is_admin_ou_gestao():
    return session.get("user_role") in ROLES_ADMINISTRATIVAS


def admin_required(f):
    """
    Admin e Gestão/Gestor acessam rotas operacionais/admin.
    Gestão/Gestor tem acesso completo ao sistema.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):

        if not session.get("user_id"):
            return redirect("/login")

        if not is_admin_ou_gestao():
            return "Acesso negado 🚫"

        return f(*args, **kwargs)

    return decorated_function


def admin_ou_gestao_required(f):
    """
    Mesma regra do admin_required.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):

        if not session.get("user_id"):
            return redirect("/login")

        if not is_admin_ou_gestao():
            return "Acesso negado 🚫"

        return f(*args, **kwargs)

    return decorated_function


def gestao_required(f):
    """
    Apenas Gestão/Gestor acessa financeiro, importações e fechamento.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):

        if not session.get("user_id"):
            return redirect("/login")

        if not is_gestao():
            return "Acesso negado 🚫"

        return f(*args, **kwargs)

    return decorated_function