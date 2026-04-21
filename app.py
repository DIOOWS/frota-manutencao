import app
from flask import Flask
from database import db
from flask_migrate import Migrate
from dotenv import load_dotenv
import os
from routes.auth import auth_bp
from routes.clientes import cliente_bp



# ==========================================
# 🔥 CARREGAR VARIÁVEIS DE AMBIENTE
# ==========================================
load_dotenv()

# ==========================================
# 🔥 CRIAR APP
# ==========================================
app = Flask(__name__)

# ==========================================
# 🔐 SECRET KEY
# ==========================================
app.config['SECRET_KEY'] = os.getenv(
    'SECRET_KEY',
    'dev-insecure-key-change-this'
)

# ==========================================
# 🔥 DETECTAR AMBIENTE
# ==========================================
ENV = os.getenv("FLASK_ENV", "development")

# ==========================================
# 🔥 CONFIGURAÇÃO DO BANCO (ÚNICA E CORRETA)
# ==========================================
if ENV == "production":
    print("🔥 USANDO BANCO DE PRODUÇÃO (SUPABASE)")

    database_url = os.getenv("DATABASE_URL_PROD")

    if not database_url:
        raise RuntimeError("🚨 DATABASE_URL_PROD não configurada!")

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    app.config['SQLALCHEMY_DATABASE_URI'] = database_url

    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "connect_args": {
            "sslmode": "require"
        }
    }

else:
    print("🔥 USANDO BANCO LOCAL (SQLITE)")

    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///dev.db"

# ==========================================
# 🔥 CONFIG GERAL
# ==========================================
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ==========================================
# 🔥 INICIAR DB
# ==========================================
db.init_app(app)
migrate = Migrate(app, db)

# ==========================================
# 🔥 IMPORTAR ROTAS
# ==========================================
from routes.dashboard import dashboard_bp
from routes.manutencoes import manutencao_bp
from routes.auth import auth_bp

app.register_blueprint(dashboard_bp)
app.register_blueprint(manutencao_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(cliente_bp)

# ==========================================
# 🔥 ROTAS DE TESTE
# ==========================================
@app.route("/")
def home():
    return "🔥 APP ONLINE"

@app.route("/teste-db")
def teste_db():
    from sqlalchemy import text
    try:
        db.session.execute(text("SELECT 1"))
        return "✅ Banco conectado!"
    except Exception as e:
        return f"❌ Erro: {str(e)}"

# ==========================================
# 🔥 RODAR LOCAL
# ==========================================
if __name__ == "__main__":
    app.run(debug=True)