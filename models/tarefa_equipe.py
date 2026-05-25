from datetime import datetime
from database import db


class TarefaEquipe(db.Model):
    __tablename__ = "tarefas_equipe"

    id = db.Column(db.Integer, primary_key=True)

    responsavel = db.Column(db.String(100), nullable=False)
    titulo = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.Text)

    dia_semana = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(30), default="PENDENTE")

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    def status_formatado(self):
        status = (self.status or "").upper()

        mapa = {
            "PENDENTE": "Pendente",
            "ANDAMENTO": "Em andamento",
            "CONCLUIDA": "Concluída",
            "CANCELADA": "Cancelada",
        }

        return mapa.get(status, status.title())

    def status_classe(self):
        status = (self.status or "").upper()

        mapa = {
            "PENDENTE": "pendente",
            "ANDAMENTO": "andamento",
            "CONCLUIDA": "concluida",
            "CANCELADA": "cancelada",
        }

        return mapa.get(status, "pendente")