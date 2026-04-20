from flask import Flask
from database import db
from flask_migrate import Migrate
from dotenv import load_dotenv
import os

# 🔥 carregar env PRIMEIRO
load_dotenv()

# 🔥 criar app
app = Flask(__name__)

# 🔥 ESSENCIAL PARA LOGIN
app.secret_key = "minha_chave_super_secreta_123"

# 🔥 configurar DEPOIS de criar
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://postgres:94BmzfxfN9hxxoTP@db.vhrkitmevkgtoudilbmo.supabase.co:5432/postgres"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 🔥 iniciar db
db.init_app(app)

# 🔥 migrate
migrate = Migrate(app, db)

# 🔥 IMPORTAR models e routes SÓ DEPOIS
from models import *
from routes.dashboard import dashboard_bp
from routes.manutencoes import manutencao_bp

# 🔥 registrar rotas
app.register_blueprint(dashboard_bp)
app.register_blueprint(manutencao_bp, url_prefix="/manutencoes")

if __name__ == "__main__":
    app.run(debug=True)