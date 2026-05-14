from functools import wraps
from flask import session, redirect


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        if not session.get("user_id"):
            return redirect("/login")

        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    """
    Admin e Gestão acessam rotas operacionais/admin.
    Gestão tem acesso completo ao sistema.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):

        if not session.get("user_id"):
            return redirect("/login")

        if session.get("user_role") not in ["admin", "gestao"]:
            return "Acesso negado 🚫"

        return f(*args, **kwargs)

    return decorated_function


def admin_ou_gestao_required(f):
    """
    Mesma regra do admin_required, mas com nome mais claro.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):

        if not session.get("user_id"):
            return redirect("/login")

        if session.get("user_role") not in ["admin", "gestao"]:
            return "Acesso negado 🚫"

        return f(*args, **kwargs)

    return decorated_function


def gestao_required(f):
    """
    Apenas Gestão acessa financeiro/importações/fechamento.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):

        if not session.get("user_id"):
            return redirect("/login")

        if session.get("user_role") != "gestao":
            return "Acesso negado 🚫"

        return f(*args, **kwargs)

    return decorated_function