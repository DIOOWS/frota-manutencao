from functools import wraps
from flask import session, redirect

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        if not session.get("user_id"):
            return redirect("/login")

        if session.get("user_role") != "admin":
            return "Acesso negado 🚫"

        return f(*args, **kwargs)

    return decorated_function