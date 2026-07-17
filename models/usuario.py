from database import db
from werkzeug.security import generate_password_hash, check_password_hash


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100))

    senha_hash = db.Column(db.String(200), nullable=False)

    role = db.Column(db.String(20), default="usuario")

    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey("clientes.id"),
        nullable=True
    )

    cliente = db.relationship(
        "Cliente",
        backref="usuarios"
    )

    foto = db.Column(db.String(255))

    # Atualizado pelo heartbeat do navegador.
    # Um usuário é considerado online quando este horário está dentro
    # da janela configurada na rota /api/usuarios-online.
    ultima_atividade = db.Column(db.DateTime, nullable=True, index=True)

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)
