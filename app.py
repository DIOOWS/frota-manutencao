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

print("🔥 DATABASE_URL:", database_url)  # DEBUG

if not database_url:
    raise RuntimeError("🚨 DATABASE_URL não configurada!")

# Corrigir prefixo antigo
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# SSL obrigatório
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "connect_args": {
        "sslmode": "require"
    }
}

# =====================================================
# 🔥 INICIAR DB
# =====================================================
db.init_app(app)
migrate = Migrate(app, db)

# =====================================================
# 🔥 ROTAS DE TESTE
# =====================================================

@app.route("/")
def home():
    return "🔥 APP ONLINE"

@app.route("/health")
def health():
    return {"status": "ok"}, 200

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