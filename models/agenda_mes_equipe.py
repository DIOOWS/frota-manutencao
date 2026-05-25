from datetime import datetime
from database import db


class AgendaMesEquipe(db.Model):
    __tablename__ = "agenda_meses_equipe"

    id = db.Column(db.Integer, primary_key=True)

    membro_id = db.Column(
        db.Integer,
        db.ForeignKey("membros_agenda_equipe.id"),
        nullable=False
    )

    mes = db.Column(db.Integer, nullable=False)
    ano = db.Column(db.Integer, nullable=False)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    membro = db.relationship(
        "MembroAgendaEquipe",
        backref=db.backref("agendas_mensais", lazy=True)
    )

    __table_args__ = (
        db.UniqueConstraint(
            "membro_id",
            "mes",
            "ano",
            name="uq_agenda_mes_membro"
        ),
        {
            "extend_existing": True
        }
    )