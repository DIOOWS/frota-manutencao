from database import db
from datetime import datetime


class PlanejamentoFinanceiro(db.Model):
    __tablename__ = "planejamento_financeiro"

    id = db.Column(db.Integer, primary_key=True)
    conta_id = db.Column(db.Integer, nullable=False)
    origem = db.Column(db.String(30), nullable=False, default="IMPORTADA")
    mes = db.Column(db.Integer, nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    status_planejamento = db.Column(db.String(30), nullable=False, default="PLANEJADA")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint(
            "conta_id",
            "origem",
            "mes",
            "ano",
            name="uq_planejamento_financeiro_conta_origem_mes_ano",
        ),
    )
