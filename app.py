from flask import Flask, redirect
from database import db
from flask_migrate import Migrate
from dotenv import load_dotenv
import os

# =====================================================
# 🔥 CARREGAR VARIÁVEIS DE AMBIENTE
# =====================================================
load_dotenv()

# =====================================================
# 🔥 CRIAR APP
# =====================================================
app = Flask(__name__)

# =====================================================
# 🔐 SECRET KEY
# =====================================================
app.config['SECRET_KEY'] = os.getenv(
    'SECRET_KEY',
    'dev-insecure-key-change-this'
)

# =====================================================
# 🔥 DATABASE (SUPABASE)
# =====================================================
database_url = os.getenv('DATABASE_URL')

print("🔥 DATABASE_URL:", database_url)  # (pode remover depois)

if not database_url:
    raise RuntimeError("🚨 DATABASE_URL não configurada!")

# Corrigir prefixo antigo
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# SSL obrigatório (Supabase)
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "connect_args": {"sslmode": "require"}
}

# =====================================================
# 🔥 INICIAR DB
# =====================================================
db.init_app(app)
migrate = Migrate(app, db)

# =====================================================
# 🔥 IMPORTS (DEPOIS DO APP + DB)
# =====================================================
from models import *
from routes.dashboard import dashboard_bp
from routes.manutencoes import manutencao_bp

# =====================================================
# 🔥 REGISTRAR ROTAS (BLUEPRINTS)
# =====================================================
app.register_blueprint(dashboard_bp)  # geralmente expõe /dashboard
app.register_blueprint(manutencao_bp, url_prefix="/manutencoes")

# =====================================================
# 🔥 HOME → DASHBOARD
# =====================================================
@app.route("/")
def home():
    return redirect("/dashboard")

# =====================================================
# 🔥 HEALTH
# =====================================================
@app.route("/health")
def health():
    return {"status": "ok"}, 200

# =====================================================
# 🔥 TESTE DB
# =====================================================
@app.route("/teste-db")
def teste_db():
    from sqlalchemy import text
    try:
        db.session.execute(text("SELECT 1"))
        return "✅ Banco conectado!", 200
    except Exception as e:
        return f"❌ Erro: {str(e)}", 500

# =====================================================
# 🔥 RODAR LOCAL
# =====================================================
if __name__ == "__main__":
    app.run(debug=True)