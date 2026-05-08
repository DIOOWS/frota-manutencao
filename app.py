from flask import Flask, request, session
from database import db
from flask_migrate import Migrate
from dotenv import load_dotenv
import os
import cloudinary
from sqlalchemy import text

from routes.frotas import frotas_bp

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
from models.afericao_termometro import AfericaoTermometro

# ==========================================
# 🚨 GARANTIR COLUNAS / TABELAS
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

    try:
        db.create_all()
        print("🔥 tabelas verificadas/criadas")
    except Exception as e:
        print("create_all:", e)

    try:
        db.session.execute(text("ALTER TABLE afericoes_termometros ADD COLUMN imagens TEXT;"))
        db.session.commit()
        print("🔥 coluna imagens criada em afericoes_termometros")
    except Exception as e:
        print("imagens afericoes_termometros:", e)

    try:
        db.session.execute(text("ALTER TABLE manutencoes ADD COLUMN dtm INTEGER;"))
        db.session.commit()
        print("🔥 coluna dtm criada em manutencoes")
    except Exception as e:
        print("dtm manutencoes:", e)

# ==========================================
# 🔥 CRIAR ADMIN
# ==========================================
with app.app_context():
    try:
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
from routes.frotas import frotas_bp

app.register_blueprint(dashboard_bp)
app.register_blueprint(manutencao_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(cliente_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(frotas_bp)

# ==========================================
# 🔧 HELPERS DE CORREÇÃO
# ==========================================
def normalizar_texto(valor):
    if valor is None:
        return None

    valor = str(valor).strip()

    if not valor:
        return None

    return " ".join(valor.split()).upper()


# ==========================================
# 🚨 ROTA TEMPORÁRIA - CORRIGIR DADOS PRODUÇÃO
# ==========================================
@app.route("/corrigir-dados-producao")
def corrigir_dados_producao():

    token_url = request.args.get("token")
    token_env = os.getenv("CORRECAO_TOKEN")

    usuario_admin = session.get("user_role") == "admin"
    token_valido = token_env and token_url == token_env

    if not usuario_admin and not token_valido:
        return "❌ Sem permissão para executar correção.", 403

    try:
        registros = Manutencao.query.all()

        total_atm_corrigido = 0
        total_textos_corrigidos = 0

        campos_texto = [
            "cliente",
            "bau",
            "tipo_veiculo",
            "tipo_servico",
            "tipo_atendimento",
            "tipo_manutencao",
            "status",
            "causa",
            "observacao",
        ]

        for m in registros:

            # =========================
            # 🔥 CORRIGIR ATM
            # =========================
            if m.data and m.data_saida:

                if m.data_saida >= m.data:
                    dias = (m.data_saida - m.data).days
                    novo_atm = max(dias, 1)

                    if m.dtm != novo_atm:
                        m.dtm = novo_atm
                        total_atm_corrigido += 1

            # =========================
            # 🔥 PADRONIZAR TEXTOS
            # =========================
            for campo in campos_texto:
                valor_atual = getattr(m, campo)
                valor_novo = normalizar_texto(valor_atual)

                if valor_atual != valor_novo:
                    setattr(m, campo, valor_novo)
                    total_textos_corrigidos += 1

        db.session.commit()

        return f"""
        ✅ Correção finalizada com sucesso!<br><br>
        ATM corrigidos: {total_atm_corrigido}<br>
        Campos de texto corrigidos: {total_textos_corrigidos}<br><br>
        ⚠️ Agora remova essa rota do app.py depois de confirmar.
        """

    except Exception as e:
        db.session.rollback()
        return f"❌ Erro ao corrigir dados: {str(e)}", 500


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