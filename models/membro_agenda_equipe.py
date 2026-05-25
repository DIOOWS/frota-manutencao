from datetime import datetime
from database import db


class MembroAgendaEquipe(db.Model):
    __tablename__ = "membros_agenda_equipe"

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(120), nullable=False)
    cargo = db.Column(db.String(120), default="Equipe")
    foto = db.Column(db.String(255))

    ativo = db.Column(db.Boolean, default=True)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )