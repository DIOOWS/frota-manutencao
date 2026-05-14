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
    Admin e Gestão têm acesso operacional completo.
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
    Alias para deixar o código mais claro em rotas operacionais.
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
    Apenas Gestão acessa a área financeira.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):

        if not session.get("user_id"):
            return redirect("/login")

        if session.get("user_role") != "gestao":
            return "Acesso negado 🚫"

        return f(*args, **kwargs)

    return decorated_function