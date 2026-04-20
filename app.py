from flask import Flask
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
# 🔐 SECRET KEY (SEGURA)
# =====================================================
app.config['SECRET_KEY'] = os.getenv(
    'SECRET_KEY',
    'dev-insecure-key-change-this'
)

# =====================================================
# 🔥 DATABASE (SUPABASE / POSTGRES)
# =====================================================
database_url = os.getenv('DATABASE_URL')

if not database_url:
    raise RuntimeError("🚨 DATABASE_URL não configurada no ambiente!")

# 🔥 Corrigir prefixo antigo do postgres
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 🔥 SSL obrigatório (Supabase / Render)
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "connect_args": {
        "sslmode": "require"
    }
}

# =====================================================
# 🔥 INICIAR BANCO
# =====================================================
db.init_app(app)

# =====================================================
# 🔥 MIGRATIONS
# =====================================================
migrate = Migrate(app, db)

# =====================================================
# 🔥 IMPORTS (DEPOIS DO APP)
# =====================================================
from models import *
from routes.dashboard import dashboard_bp
from routes.manutencoes import manutencao_bp

@app.route("/")
def home():
    return "ok"

# =====================================================
# 🔥 REGISTRAR ROTAS
# =====================================================
# app.register_blueprint(dashboard_bp)
# app.register_blueprint(manutencao_bp, url_prefix="/manutencoes")

@app.route("/teste-db")
def teste_db():
    from sqlalchemy import text
    try:
        db.session.execute(text("SELECT 1"))
        return "Banco conectado!", 200
    except Exception as e:
        return str(e), 500

# =====================================================
# 🔥 HEALTH CHECK (IMPORTANTE PRO RENDER)
# =====================================================
@app.route("/health")
def health():
    return {"status": "ok"}, 200

# =====================================================
# 🔥 RODAR LOCAL
# =====================================================
if __name__ == "__main__":
    app.run(debug=True)