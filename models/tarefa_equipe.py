from datetime import datetime
from database import db


class TarefaEquipe(db.Model):
    __tablename__ = "agenda_tarefas_equipe"

    id = db.Column(db.Integer, primary_key=True)

    membro_id = db.Column(
        db.Integer,
        db.ForeignKey("membros_agenda_equipe.id"),
        nullable=False
    )

    titulo = db.Column(db.String(180), nullable=False)
    descricao = db.Column(db.Text)

    mes = db.Column(db.Integer, nullable=False)
    ano = db.Column(db.Integer, nullable=False)

    periodicidade = db.Column(db.String(30), default="DIARIA")
    dia_semana = db.Column(db.Integer)
    dia_mes = db.Column(db.Integer)

    ativo = db.Column(db.Boolean, default=True)
    ordem = db.Column(db.Integer, default=0)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    membro = db.relationship(
        "MembroAgendaEquipe",
        backref=db.backref("tarefas_agenda", lazy=True)
    )

    def periodicidade_formatada(self):
        mapa = {
            "DIARIA": "Diário",
            "SEMANAL": "Semanal",
            "MENSAL": "Mensal",
            "EXTRA": "Extra",
        }

        return mapa.get((self.periodicidade or "").upper(), "Diário")


class ExecucaoTarefaEquipe(db.Model):
    __tablename__ = "agenda_execucoes_tarefas"

    id = db.Column(db.Integer, primary_key=True)

    tarefa_id = db.Column(
        db.Integer,
        db.ForeignKey("agenda_tarefas_equipe.id"),
        nullable=False
    )

    data = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(30), default="PENDENTE")

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    tarefa = db.relationship(
        "TarefaEquipe",
        backref=db.backref(
            "execucoes",
            lazy=True,
            cascade="all, delete-orphan"
        )
    )

    def status_formatado(self):
        status = (self.status or "").upper()

        mapa = {
            "PENDENTE": "Pendente",
            "CONCLUIDA": "OK",
            "CANCELADA": "Cancelada",
        }

        return mapa.get(status, status.title())

    def status_classe(self):
        status = (self.status or "").upper()

        mapa = {
            "PENDENTE": "pendente",
            "CONCLUIDA": "concluida",
            "CANCELADA": "cancelada",
        }

        return mapa.get(status, "pendente")