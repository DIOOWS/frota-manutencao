from flask import Flask, send_from_directory
from database import db
from flask_migrate import Migrate
from dotenv import load_dotenv
import os
import cloudinary
from sqlalchemy import text, inspect

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
app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "dev-insecure-key-change-this"
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

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url

    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "connect_args": {"sslmode": "require"}
    }

else:
    print("🔥 USANDO SQLITE LOCAL")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///dev.db"

# ==========================================
# 🔧 CONFIG
# ==========================================
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

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
from models.lancamento_financeiro import LancamentoFinanceiro
from models.fechamento_mensal import FechamentoMensal
from models.conta_pagar_importada import ContaPagarImportada
from models.conta_receber_importada import ContaReceberImportada
from models.membro_agenda_equipe import MembroAgendaEquipe
from models.agenda_mes_equipe import AgendaMesEquipe
from models.tarefa_equipe import TarefaEquipe, ExecucaoTarefaEquipe
from models.conta_recorrente import ContaRecorrente
from models.causa_manutencao import CausaManutencao
from models.problema_manutencao import ProblemaManutencao



# ==========================================
# 🧱 HELPERS DE BANCO
# ==========================================
def tabela_existe(nome_tabela):
    inspector = inspect(db.engine)
    return nome_tabela in inspector.get_table_names()


def coluna_existe(nome_tabela, nome_coluna):
    if not tabela_existe(nome_tabela):
        return False

    inspector = inspect(db.engine)
    colunas = inspector.get_columns(nome_tabela)

    return any(coluna["name"] == nome_coluna for coluna in colunas)


def garantir_coluna(nome_tabela, nome_coluna, definicao_sql):
    try:
        if not tabela_existe(nome_tabela):
            print(f"⚠️ tabela {nome_tabela} ainda não existe.")
            return

        if coluna_existe(nome_tabela, nome_coluna):
            print(f"✅ coluna {nome_coluna} já existe em {nome_tabela}")
            return

        db.session.execute(
            text(f"ALTER TABLE {nome_tabela} ADD COLUMN {nome_coluna} {definicao_sql};")
        )
        db.session.commit()

        print(f"🔥 coluna {nome_coluna} criada em {nome_tabela}")

    except Exception as e:
        db.session.rollback()
        print(f"❌ erro ao criar coluna {nome_coluna} em {nome_tabela}: {e}")


# ==========================================
# 🚨 GARANTIR TABELAS / COLUNAS
# ==========================================
with app.app_context():
    try:
        db.create_all()
        print("🔥 tabelas verificadas/criadas")
    except Exception as e:
        print("create_all:", e)

    garantir_coluna(
        nome_tabela="usuarios",
        nome_coluna="role",
        definicao_sql="VARCHAR(20)"
    )

    garantir_coluna(
        nome_tabela="usuarios",
        nome_coluna="foto",
        definicao_sql="VARCHAR(255)"
    )

    garantir_coluna(
        nome_tabela="afericoes_termometros",
        nome_coluna="imagens",
        definicao_sql="TEXT"
    )

    garantir_coluna(
        nome_tabela="manutencoes",
        nome_coluna="dtm",
        definicao_sql="INTEGER"
    )

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
        db.session.rollback()
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
from routes.assistente import assistente_bp
from routes.gestao import gestao_bp
from routes.importacoes import importacoes_bp
from routes.radar_financeiro import radar_financeiro_bp
from routes.agenda_equipe import agenda_equipe_bp

app.register_blueprint(dashboard_bp)
app.register_blueprint(manutencao_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(cliente_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(frotas_bp)
app.register_blueprint(assistente_bp)
app.register_blueprint(gestao_bp)
app.register_blueprint(importacoes_bp)
app.register_blueprint(radar_financeiro_bp)
app.register_blueprint(agenda_equipe_bp)


# ==========================================
# 🌐 FAVICON
# ==========================================
@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static", "css", "img"),
        "logo.png",
        mimetype="image/png"
    )


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