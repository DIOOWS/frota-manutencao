from flask import Flask
from database import db
from flask_migrate import Migrate
from dotenv import load_dotenv
import os

# ==========================================
# 🔥 CARREGAR VARIÁVEIS DE AMBIENTE
# ==========================================
load_dotenv()

# ==========================================
# 🔥 CRIAR APP
# ==========================================
app = Flask(__name__, template_folder="templates")

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
# 🔥 CONFIGURAÇÃO DO BANCO
# ==========================================
if ENV == "production":
    print("🔥 USANDO BANCO DE PRODUÇÃO (SUPABASE)")

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("🚨 DATABASE_URL não configurada!")

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
# 🔥 IMPORTAR MODELS (ESSENCIAL)
# ==========================================
from models.usuario import Usuario
from models.cliente import Cliente
from models.manutencao import Manutencao

# ==========================================
# 🔥 CRIAR TABELAS AUTOMATICAMENTE
# ==========================================
with app.app_context():
    try:
        db.create_all()
        print("🔥 Tabelas criadas com sucesso!")
    except Exception as e:
        print("❌ Erro ao criar tabelas:", e)

        from models.usuario import Usuario

        with app.app_context():
            try:
                if not Usuario.query.filter_by(nome="admin").first():

                    admin = Usuario(
                        nome="admin",
                        email="admin@admin.com"
                    )
                    admin.set_senha("123")

                    db.session.add(admin)
                    db.session.commit()

                    print("🔥 ADMIN CRIADO: admin / 123")

                else:
                    print("ℹ️ ADMIN já existe")

            except Exception as e:
                print("❌ Erro ao criar admin:", e)

# ==========================================
# 🔥 GARANTIR COLUNA 'os' (PRODUÇÃO)
# ==========================================
from sqlalchemy import text

with app.app_context():
    try:
        db.session.execute(text("ALTER TABLE manutencoes ADD COLUMN os VARCHAR(50);"))
        db.session.commit()
        print("🔥 Coluna 'os' criada!")
    except Exception as e:
        print("ℹ️ Coluna 'os' já existe ou erro ignorado:", e)

# ==========================================
# 🔥 IMPORTAR ROTAS
# ==========================================
from routes.dashboard import dashboard_bp
from routes.manutencoes import manutencao_bp
from routes.auth import auth_bp
from routes.clientes import cliente_bp
from routes.admin import admin_bp

app.register_blueprint(dashboard_bp)
app.register_blueprint(manutencao_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(cliente_bp)
app.register_blueprint(admin_bp)

# ==========================================
# 🔥 ROTAS DE TESTE
# ==========================================
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