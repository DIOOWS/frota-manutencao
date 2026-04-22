from flask import Flask
from database import db
from flask_migrate import Migrate
from dotenv import load_dotenv
import os
import cloudinary
from sqlalchemy import text

# ==========================================
# 🔥 CARREGAR VARIÁVEIS
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
# ☁️ CLOUDINARY
# ==========================================
cloudinary.config(
    cloud_name=os.getenv("CLOUD_NAME"),
    api_key=os.getenv("API_KEY"),
    api_secret=os.getenv("API_SECRET")
)

# ==========================================
# 🔥 AMBIENTE
# ==========================================
ENV = os.getenv("FLASK_ENV", "development")

# ==========================================
# 🔥 BANCO
# ==========================================
if ENV == "production":
    print("🔥 USANDO BANCO DE PRODUÇÃO")

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("🚨 DATABASE_URL não configurada!")

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    app.config['SQLALCHEMY_DATABASE_URI'] = database_url

    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "connect_args": {"sslmode": "require"}
    }

else:
    print("🔥 USANDO SQLITE LOCAL")
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///dev.db"

# ==========================================
# 🔧 CONFIG
# ==========================================
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ==========================================
# 📷 UPLOAD LOCAL (fallback)
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ==========================================
# 🔥 INICIAR DB
# ==========================================
db.init_app(app)
migrate = Migrate(app, db)

# ==========================================
# 🔥 IMPORTAR MODELS
# ==========================================
from models.usuario import Usuario
from models.cliente import Cliente
from models.manutencao import Manutencao

# ==========================================
# 🚨 GARANTIR COLUNAS (ANTES DE QUALQUER QUERY)
# ==========================================
with app.app_context():
    try:
        db.session.execute(text("ALTER TABLE usuarios ADD COLUMN role VARCHAR(20);"))
        db.session.commit()
        print("🔥 role criada")
    except Exception as e:
        print("role:", e)

    try:
        db.session.execute(text("ALTER TABLE usuarios ADD COLUMN foto VARCHAR(255);"))
        db.session.commit()
        print("🔥 foto criada")
    except Exception as e:
        print("foto:", e)

# ==========================================
# 🔥 CRIAR ADMIN (DEPOIS DAS COLUNAS)
# ==========================================
with app.app_context():
    try:
        db.create_all()

        if not Usuario.query.filter_by(nome="admin").first():
            admin = Usuario(
                nome="admin",
                email="admin@admin.com",
                role="admin"
            )
            admin.set_senha("123")

            db.session.add(admin)
            db.session.commit()

            print("🔥 ADMIN CRIADO: admin / 123")

    except Exception as e:
        print("❌ ERRO AO INICIAR DB:", e)

# ==========================================
# 🔥 ROTAS
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
# 🔥 TESTE
# ==========================================
@app.route("/teste-db")
def teste_db():
    try:
        db.session.execute(text("SELECT 1"))
        return "✅ Banco conectado!"
    except Exception as e:
        return f"❌ Erro: {str(e)}"

# ==========================================
# 🚀 START
# ==========================================
if __name__ == "__main__":
    app.run(debug=True)